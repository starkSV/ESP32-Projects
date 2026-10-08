// ESP32 watchdog for a laptop-as-server, using Intel AMT for the actual reset.
//
// What it does:
//   * every POLL_MS it checks the server from the outside:
//       - TCP connect to :22        (kernel + network stack alive)
//       - real DNS query to :53     (AdGuard actually answers, not just "container is Up")
//       - a control target (NAS)    (so a router/Wi-Fi problem never triggers a reset)
//   * server dead for DEAD_AFTER_MS and the control target is fine -> ask AMT for the power state,
//       on  -> power cycle,  off -> power up
//   * after acting it waits GRACE_MS; after MAX_FAILED_RECOVERIES failed recoveries it latches and
//     only alerts, so it can never boot-loop the machine.
//   * "degraded" (SSH ok but DNS dead, or the reverse) never resets anything; it is only logged.
//   * ntfy lives on the server, so alerts are queued and delivered once the server is back.
//   * BOOT button (GPIO0) pauses the watchdog for up to PAUSE_MAX_MS for planned maintenance.
//
// DRY_RUN defaults to 1: it logs what it WOULD do and sends nothing to AMT. Set it to 0 only after
// the read-only AMT check and the dry-run soak have both looked right.

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Preferences.h>
#include <MD5Builder.h>
#include "secrets.h"

#ifndef DRY_RUN
#define DRY_RUN 0
#endif

// 1 = pretend the SSH/DNS probes fail, so the whole decision path (including a real, read-only AMT
// power-state query) can be tested without touching the server. Keep DRY_RUN at 1 while testing this.
#ifndef SIMULATE_DEAD
#define SIMULATE_DEAD 0
#endif

// Defined up here on purpose: Arduino auto-generates function prototypes near the top of the
// file, and they must be able to see this type.
struct WsResult { bool ok; int status; String body; };

// ---- tuning -------------------------------------------------------------------------------
static const uint32_t POLL_MS        = 15000UL;
static const uint32_t DEAD_AFTER_MS  = SIMULATE_DEAD ? 30UL * 1000UL : 5UL * 60UL * 1000UL;  // a normal reboot takes ~1 min
static const uint32_t GRACE_MS       = 8UL * 60UL * 1000UL;   // time allowed for a recovery
static const uint32_t PAUSE_MAX_MS   = 60UL * 60UL * 1000UL;  // pause auto-expires
static const int      MAX_FAILED_RECOVERIES = 3;
static const int      PAUSE_PIN      = 0;                     // BOOT button on most devkits
static const char*    DNS_TEST_NAME  = "github.com";

// AMT PowerState values (CIM_PowerManagementService): 2 = on, 5 = power cycle, 8 = power down
static const int AMT_ON = 2, AMT_CYCLE = 5;

// ---- state --------------------------------------------------------------------------------
static IPAddress serverIp, controlIp;
static Preferences prefs;

static uint32_t deadSince = 0;       // 0 = not currently dead
static uint32_t graceUntil = 0;
static bool     inRecovery = false;
static uint32_t actedAt = 0;
static int      failedRecoveries = 0;
static bool     latched = false;
static bool     paused = false;
static uint32_t pausedAt = 0;
static uint32_t degradedPolls = 0;

static String   pending[4];
static int      npending = 0;

static void wlog(const char* fmt, ...) {
  char buf[200];
  va_list ap; va_start(ap, fmt); vsnprintf(buf, sizeof(buf), fmt, ap); va_end(ap);
  Serial.printf("[%8lus] %s\n", (unsigned long)(millis() / 1000), buf);
}

static void queueNote(const String& msg) {
  wlog("note queued: %s", msg.c_str());
  if (npending < 4) pending[npending++] = msg;
}

// ---- probes -------------------------------------------------------------------------------
static bool tcpProbe(IPAddress ip, uint16_t port, int32_t timeoutMs = 2000) {
  WiFiClient c;
  bool ok = c.connect(ip, port, timeoutMs);
  c.stop();
  return ok;
}

static bool dnsProbe(IPAddress server, const char* name, uint32_t timeoutMs = 2500) {
  WiFiUDP udp;
  if (!udp.begin(40000 + (esp_random() % 2000))) return false;

  uint8_t pkt[96]; size_t n = 0;
  uint16_t id = (uint16_t)esp_random();
  pkt[n++] = id >> 8; pkt[n++] = id & 0xFF;
  pkt[n++] = 0x01; pkt[n++] = 0x00;                 // standard query, recursion desired
  pkt[n++] = 0; pkt[n++] = 1;                       // QDCOUNT = 1
  for (int i = 0; i < 6; i++) pkt[n++] = 0;         // AN/NS/AR = 0
  const char* p = name;
  while (*p) {
    const char* dot = strchr(p, '.');
    size_t len = dot ? (size_t)(dot - p) : strlen(p);
    pkt[n++] = (uint8_t)len;
    memcpy(pkt + n, p, len); n += len;
    p += len; if (*p == '.') p++;
  }
  pkt[n++] = 0;
  pkt[n++] = 0; pkt[n++] = 1;                       // QTYPE A
  pkt[n++] = 0; pkt[n++] = 1;                       // QCLASS IN

  bool ok = false;
  if (udp.beginPacket(server, 53)) {
    udp.write(pkt, n);
    if (udp.endPacket()) {
      uint32_t t0 = millis();
      while (millis() - t0 < timeoutMs) {
        int sz = udp.parsePacket();
        if (sz >= 12) {
          uint8_t buf[512];
          int r = udp.read(buf, sizeof(buf));
          if (r >= 12 && buf[0] == (id >> 8) && buf[1] == (id & 0xFF)) {
            bool isResponse = buf[2] & 0x80;
            uint8_t rcode = buf[3] & 0x0F;
            uint16_t answers = ((uint16_t)buf[6] << 8) | buf[7];
            ok = isResponse && rcode == 0 && answers > 0;
            break;
          }
        }
        delay(10);
      }
    }
  }
  udp.stop();
  return ok;
}

// ---- AMT WS-Management over HTTP with digest auth -----------------------------------------
static String md5hex(const String& s) {
  MD5Builder m; m.begin(); m.add(s); m.calculate(); return m.toString();
}

static String rawExchange(const String& request, uint32_t timeoutMs = 6000) {
  WiFiClient c;
  if (!c.connect(serverIp, AMT_PORT, 3000)) return "";
  c.print(request);
  String resp; uint32_t t0 = millis();
  while ((c.connected() || c.available()) && millis() - t0 < timeoutMs && resp.length() < 6000) {
    while (c.available() && resp.length() < 6000) resp += (char)c.read();
    delay(5);
  }
  c.stop();
  return resp;
}

static String buildRequest(const String& body, const String& auth) {
  String r = "POST /wsman HTTP/1.1\r\nHost: " + String(SERVER_HOST) + ":" + String(AMT_PORT) + "\r\n";
  r += "Content-Type: application/soap+xml;charset=UTF-8\r\n";
  r += "Content-Length: " + String(body.length()) + "\r\n";
  r += "Connection: close\r\n";
  if (auth.length()) r += "Authorization: " + auth + "\r\n";
  r += "\r\n" + body;
  return r;
}

static int statusCode(const String& resp) {            // "HTTP/1.1 200 OK"
  if (resp.length() < 12) return 0;
  return resp.substring(9, 12).toInt();
}

static String headerValue(const String& resp, const char* name) {
  String low = resp; low.toLowerCase();
  String key = String(name); key.toLowerCase(); key += ":";
  int i = low.indexOf(key);
  if (i < 0) return "";
  int e = resp.indexOf("\r\n", i);
  return resp.substring(i + key.length(), e < 0 ? resp.length() : e);
}

static String bodyOf(const String& resp) {
  int i = resp.indexOf("\r\n\r\n");
  return i < 0 ? "" : resp.substring(i + 4);
}

static String digestParam(const String& hdr, const char* key) {   // key="value"
  String k = String(key) + "=\"";
  int i = hdr.indexOf(k);
  if (i < 0) return "";
  i += k.length();
  int e = hdr.indexOf('"', i);
  return e < 0 ? "" : hdr.substring(i, e);
}

static String makeAuth(const String& www) {
  String realm = digestParam(www, "realm");
  String nonce = digestParam(www, "nonce");
  String opaque = digestParam(www, "opaque");
  if (!nonce.length()) return "";
  String cnonce = md5hex(String(esp_random()) + String(micros())).substring(0, 16);
  const char* nc = "00000001";
  String ha1 = md5hex(String(AMT_USER) + ":" + realm + ":" + String(AMT_PASS));
  String ha2 = md5hex("POST:/wsman");
  String resp = md5hex(ha1 + ":" + nonce + ":" + nc + ":" + cnonce + ":auth:" + ha2);
  String a = "Digest username=\"" + String(AMT_USER) + "\", realm=\"" + realm + "\", nonce=\"" + nonce +
             "\", uri=\"/wsman\", cnonce=\"" + cnonce + "\", nc=" + nc + ", qop=auth, response=\"" + resp + "\"";
  if (opaque.length()) a += ", opaque=\"" + opaque + "\"";
  return a;
}


static WsResult wsman(const String& body) {
  String r1 = rawExchange(buildRequest(body, ""));
  if (!r1.length()) return {false, 0, ""};
  int st = statusCode(r1);
  if (st != 401) return {st == 200, st, bodyOf(r1)};
  String auth = makeAuth(headerValue(r1, "WWW-Authenticate"));
  if (!auth.length()) return {false, 401, ""};
  String r2 = rawExchange(buildRequest(body, auth));
  st = statusCode(r2);
  return {st == 200, st, bodyOf(r2)};
}

static const char ENV_OPEN[] =
  "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
  "<Envelope xmlns=\"http://www.w3.org/2003/05/soap-envelope\""
  " xmlns:a=\"http://schemas.xmlsoap.org/ws/2004/08/addressing\""
  " xmlns:w=\"http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd\""
  " xmlns:p=\"http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_PowerManagementService\">";

static const char REPLY_TO[] =
  "<a:ReplyTo><a:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</a:Address></a:ReplyTo>";

// Read-only: returns the AMT power state (2 = on) or -1 if AMT can't be read.
static int amtPowerState() {
  String body = String(ENV_OPEN) +
    "<Header><a:Action>http://schemas.xmlsoap.org/ws/2004/09/transfer/Get</a:Action><a:To>/wsman</a:To>"
    "<w:ResourceURI>http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_AssociatedPowerManagementService</w:ResourceURI>"
    "<a:MessageID>1</a:MessageID>" + REPLY_TO + "<w:OperationTimeout>PT30S</w:OperationTimeout></Header><Body/></Envelope>";
  WsResult r = wsman(body);
  if (!r.ok) { wlog("AMT read failed, http %d", r.status); return -1; }
  int i = r.body.indexOf(":PowerState>");
  if (i < 0) i = r.body.indexOf("<PowerState>");
  if (i < 0) return -1;
  i = r.body.indexOf('>', i) + 1;
  return r.body.substring(i).toInt();
}

static bool amtRequestPowerState(int state) {
  String body = String(ENV_OPEN) +
    "<Header><a:Action>http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_PowerManagementService/RequestPowerStateChange</a:Action>"
    "<a:To>/wsman</a:To><w:ResourceURI>http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_PowerManagementService</w:ResourceURI>"
    "<a:MessageID>2</a:MessageID>" + REPLY_TO + "<w:OperationTimeout>PT30S</w:OperationTimeout>"
    "<w:SelectorSet>"
    "<w:Selector Name=\"Name\">Intel(r) AMT Power Management Service</w:Selector>"
    "<w:Selector Name=\"SystemName\">Intel(r) AMT</w:Selector>"
    "<w:Selector Name=\"CreationClassName\">CIM_PowerManagementService</w:Selector>"
    "<w:Selector Name=\"SystemCreationClassName\">CIM_ComputerSystem</w:Selector>"
    "</w:SelectorSet></Header><Body><p:RequestPowerStateChange_INPUT><p:PowerState>" + String(state) + "</p:PowerState>"
    "<p:ManagedElement><a:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</a:Address>"
    "<a:ReferenceParameters><w:ResourceURI>http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ComputerSystem</w:ResourceURI>"
    "<w:SelectorSet><w:Selector Name=\"CreationClassName\">CIM_ComputerSystem</w:Selector>"
    "<w:Selector Name=\"Name\">ManagedSystem</w:Selector></w:SelectorSet></a:ReferenceParameters></p:ManagedElement>"
    "</p:RequestPowerStateChange_INPUT></Body></Envelope>";
  WsResult r = wsman(body);
  bool ok = r.ok && (r.body.indexOf(":ReturnValue>0<") >= 0 || r.body.indexOf("<ReturnValue>0<") >= 0);
  wlog("AMT RequestPowerStateChange(%d): http %d, %s", state, r.status, ok ? "accepted" : "rejected");
  return ok;
}

// ---- notifications (ntfy runs on the server, so only flush when it is up) -----------------
static void flushNotes() {
  while (npending > 0) {
    WiFiClient c;
    if (!c.connect(serverIp, NTFY_PORT, 2000)) return;
    String msg = pending[0];
    String req = "POST /" NTFY_TOPIC " HTTP/1.1\r\nHost: " + String(SERVER_HOST) +
                 "\r\nTitle: Server watchdog\r\nContent-Length: " + String(msg.length()) +
                 "\r\nConnection: close\r\n\r\n" + msg;
    c.print(req);
    uint32_t t0 = millis(); String line;
    while (millis() - t0 < 3000 && !c.available()) delay(10);
    if (c.available()) line = c.readStringUntil('\n');
    c.stop();
    if (line.indexOf(" 200") < 0) return;           // retry next poll
    for (int i = 1; i < npending; i++) pending[i - 1] = pending[i];
    npending--;
  }
}

// ---- recovery -----------------------------------------------------------------------------
static void recover() {
  int ps = amtPowerState();
  if (ps < 0) {
    queueNote("Server is down but AMT did not answer, so I could not reset it. Check it by hand.");
    return;
  }
  int target = (ps == AMT_ON) ? AMT_CYCLE : AMT_ON;     // on -> cycle, anything else -> power up
  const char* what = (target == AMT_CYCLE) ? "power cycle" : "power up";
#if DRY_RUN
  queueNote(String("DRY RUN: would send AMT ") + what + " (AMT reports power state " + String(ps) + ").");
#else
  bool ok = amtRequestPowerState(target);
  queueNote(String("Server unresponsive for ") + String(DEAD_AFTER_MS / 60000) + " min. Sent AMT " + what +
            (ok ? " (accepted)." : " (REJECTED by AMT)."));
#endif
  inRecovery = true; actedAt = millis(); graceUntil = millis() + GRACE_MS; deadSince = 0;
#if !DRY_RUN
  prefs.putUInt("acts", prefs.getUInt("acts", 0) + 1);
#endif
}

// ---- setup / loop -------------------------------------------------------------------------
static void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) delay(250);
  wlog("wifi %s, ip %s", WiFi.status() == WL_CONNECTED ? "up" : "DOWN", WiFi.localIP().toString().c_str());
}

void setup() {
  Serial.begin(115200);
  delay(300);
  serverIp.fromString(SERVER_HOST);
  controlIp.fromString(CONTROL_HOST);
  pinMode(PAUSE_PIN, INPUT_PULLUP);
#ifdef LED_BUILTIN
  pinMode(LED_BUILTIN, OUTPUT);
#endif
  prefs.begin("watchdog", false);
  latched = prefs.getBool("latched", false);
  wlog("boot. DRY_RUN=%d, lifetime actions=%u, latched=%d", DRY_RUN, prefs.getUInt("acts", 0), latched);
  connectWifi();
}

static uint32_t lastPoll = 0, lastBtn = 0;

void loop() {
  uint32_t now = millis();

  // BOOT button toggles pause (debounced)
  if (digitalRead(PAUSE_PIN) == LOW && now - lastBtn > 400) {
    lastBtn = now;
    paused = !paused; pausedAt = now;
    if (!paused) deadSince = 0;
    wlog("watchdog %s", paused ? "PAUSED" : "resumed");
  }
  if (paused && now - pausedAt > PAUSE_MAX_MS) { paused = false; deadSince = 0; wlog("pause expired, resumed"); }

#ifdef LED_BUILTIN
  digitalWrite(LED_BUILTIN, paused ? ((now / 1000) % 2) : (latched ? ((now / 250) % 2) : LOW));
#endif

  if (now - lastPoll < POLL_MS && lastPoll != 0) { delay(20); return; }
  lastPoll = now;

  if (WiFi.status() != WL_CONNECTED) { wlog("wifi down, not judging the server"); WiFi.reconnect(); deadSince = 0; return; }

  bool ssh = tcpProbe(serverIp, 22);
  bool dns = dnsProbe(serverIp, DNS_TEST_NAME);
  bool control = tcpProbe(controlIp, CONTROL_PORT);
  if (npending > 0 && (ssh || dns)) flushNotes();        // server is reachable: deliver queued alerts
#if SIMULATE_DEAD
  ssh = false; dns = false;                              // pretend the server is dead
#endif
  wlog("ssh=%d dns=%d control=%d%s%s%s%s", ssh, dns, control, DRY_RUN ? " [dry-run]" : " [LIVE]",
       SIMULATE_DEAD ? " [simulating dead]" : "", paused ? " [paused]" : "", latched ? " [latched]" : "");

  if (ssh && dns) {                                       // healthy
    if (inRecovery) {
      queueNote(String("Server recovered ") + String((now - actedAt) / 1000) + " s after the reset.");
      inRecovery = false; failedRecoveries = 0;
      if (latched) { latched = false; prefs.putBool("latched", false); }
    }
    deadSince = 0; degradedPolls = 0;
    flushNotes();
    return;
  }

  if (ssh || dns) {                                       // degraded: alert only, never reset
    deadSince = 0;
    if (++degradedPolls == 8) queueNote(String("Server is up but degraded (ssh=") + ssh + ", dns=" + dns +
                                        "). Not resetting; check the service.");
    return;
  }

  degradedPolls = 0;
  if (!control) { wlog("server and control both unreachable: network problem, doing nothing"); deadSince = 0; return; }
  if (paused) return;

  if (inRecovery && now > graceUntil) {                   // grace expired without recovery
    inRecovery = false; failedRecoveries++;
    wlog("recovery failed (%d/%d)", failedRecoveries, MAX_FAILED_RECOVERIES);
    if (failedRecoveries >= MAX_FAILED_RECOVERIES) {
      latched = true; prefs.putBool("latched", true);
      queueNote("Server still down after repeated resets. Watchdog latched and will not act again until it sees the server healthy.");
    }
  }
  if (inRecovery || latched) return;

  if (deadSince == 0) { deadSince = now; wlog("server looks dead, starting the %lu s timer", (unsigned long)(DEAD_AFTER_MS / 1000)); }
  if (now - deadSince >= DEAD_AFTER_MS) recover();
}
