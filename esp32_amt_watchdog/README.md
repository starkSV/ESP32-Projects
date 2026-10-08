# esp32-amt-watchdog

A $5 ESP32 that watches a home server from the outside and power-cycles it through Intel AMT when it freezes.

I built this for a Dell Latitude 7480 running as a Debian + Docker home server. A laptop's battery defeats the usual relay-on-the-power-cord trick, and the built-in iTCO hardware watchdog never reset this machine, so the reset goes through the chipset's out-of-band management engine instead. No relay, no soldering, nothing installed on the server.

> **Status:** one machine, one real test. It worked, but treat it as a well-tested experiment, not a product. See [Limitations](#limitations).

## How it works

Every 15 seconds the ESP32 runs three probes against the network:

| Probe | What it checks |
| --- | --- |
| TCP connect to the server on port 22 | The kernel and network stack are alive |
| A real DNS query (`github.com`) sent to the server's port 53 | The DNS service (AdGuard Home in my case) actually answers, not just "the container says Up" |
| TCP connect to a **control host** (my NAS) | The network and the ESP32's own Wi-Fi are fine |

Then it decides:

- **Healthy** (SSH and DNS both answer): nothing happens. Queued alerts are delivered.
- **Degraded** (only one of the two answers): never resets anything. After 8 polls (about 2 minutes) it sends an alert.
- **Dead** (both fail, and the control host answers): starts a timer. If the server is still dead after **5 minutes**, it asks AMT for the power state, then sends a power cycle (or a power up, if the machine is off).
- **Network problem** (server and control host both unreachable): does nothing. Cycling the server would not help.

Safety rails:

- **Grace period:** after acting, it waits 8 minutes before judging again.
- **Latch:** after 3 failed recoveries in a row it stops acting and only alerts, so a broken machine is never boot-looped. The latch clears once the server is seen healthy again, and it survives an ESP32 reboot.
- **Pause:** press the BOOT button to pause the watchdog for planned maintenance (auto-expires after 60 minutes). Press again to resume.
- **Dry run:** `DRY_RUN` defaults to `1`. It logs what it *would* do and sends nothing to AMT.

If you use [ntfy](https://ntfy.sh), alerts are posted to a topic. If ntfy runs on the server you are watching, as it does for me, alerts are queued on the ESP32 and delivered once the server is back.

## Requirements

- A machine with **Intel AMT** (vPro), provisioned, and on a **wired** Ethernet connection. I used AMT 11.8 on a Latitude 7480.
- An ESP32 dev board (tested: ESP32 Dev Module with a CP210x USB-UART) on a **2.4 GHz** Wi-Fi network.
- Something else that is always on, to use as the control host (a NAS, a router, a Pi).
- Arduino IDE with the `esp32` board package. Tested with Arduino IDE 2.3.10 and `esp32` core 3.3.12.
- Optional: an ntfy server and topic for alerts.

## Setup

### 1. Provision AMT

Enter the MEBx menu at boot (on many Dell machines this is `Ctrl+P`), set an AMT password, enable network access, and set user consent to KVM so power commands do not need an on-screen code. Details vary by vendor and AMT version, so check yours.

The AMT web interface shares the machine's IP and answers on port **16992**. From another computer (not the server itself) open `http://SERVER_IP:16992`. The user is `admin` and the password is the MEBx one.

### 2. Check AMT from another machine

`examples/get-power-state.xml` is a read-only request. It does not change anything.

```
curl --digest -u admin:YOUR_AMT_PASSWORD \
  -H "Content-Type: application/soap+xml;charset=UTF-8" \
  -d @examples/get-power-state.xml \
  http://SERVER_IP:16992/wsman
```

On Windows PowerShell use `curl.exe`. A healthy reply includes `PowerState` (2 means on) and the list of power states AMT will accept. On my machine those were 10, 8, 5 and 11, and the sketch uses 5 (power cycle) and 2 (power up).

### 3. Configure

```
cd esp32_amt_watchdog
cp secrets.example.h secrets.h
```

Edit `secrets.h` with your Wi-Fi, the server's IP, the AMT password, the control host and your ntfy topic. `secrets.h` is in `.gitignore`. Never commit it.

### 4. Flash

Open `esp32_amt_watchdog/esp32_amt_watchdog.ino` in the Arduino IDE, choose your board (`ESP32 Dev Module`) and port, and upload. If the upload hangs at "Connecting...", hold the BOOT button until it starts. Open the Serial Monitor at 115200 baud. A healthy server logs `ssh=1 dns=1 control=1`.

## Test it in this order

1. **Read-only AMT check** (step 2 above).
2. **Dry-run soak:** leave `DRY_RUN` at `1` for a while with the server untouched. It should stay quiet.
3. **Simulated failure:** set `SIMULATE_DEAD` to `1` (keep `DRY_RUN` at `1`). The probes are forced to fail and the timer drops to 30 seconds. After it expires the ESP32 does a real, read-only AMT power-state query and queues a `DRY RUN: would send AMT power cycle` note. This proves the AMT login works end to end without touching the server. Set `SIMULATE_DEAD` back to `0` afterwards.
4. **Real test:** set `DRY_RUN` to `0` and crash the server on purpose.

> **Warning:** step 4 is a hard power cut. Stop services with databases first, run `sync`, and make sure you have backups. I used `echo c | sudo tee /proc/sysrq-trigger` to crash the kernel and let the ESP32 do the rest.

Re-flashing restarts the ESP32's timers, so a test that spans a re-flash will take longer than 5 minutes.

## Configuration

Constants at the top of `esp32_amt_watchdog.ino`:

| Name | Default | Meaning |
| --- | --- | --- |
| `DRY_RUN` | `1` | Log only, never send a command to AMT |
| `SIMULATE_DEAD` | `0` | Force the SSH and DNS probes to fail, for testing |
| `POLL_MS` | 15 s | Time between probe rounds |
| `DEAD_AFTER_MS` | 5 min | How long the server must look dead before acting |
| `GRACE_MS` | 8 min | Time allowed for a recovery after acting |
| `MAX_FAILED_RECOVERIES` | 3 | Failed recoveries before it latches |
| `PAUSE_MAX_MS` | 60 min | The BOOT-button pause auto-expires after this |
| `DNS_TEST_NAME` | `github.com` | Name used in the DNS probe |

Endpoints live in `secrets.h`: `SERVER_HOST`, `AMT_PORT` (16992), `AMT_USER`, `AMT_PASS`, `CONTROL_HOST`, `CONTROL_PORT`, `NTFY_PORT` and `NTFY_TOPIC`.

The on-board LED blinks slowly while paused and quickly while latched.

## Security

- AMT's web interface on port 16992 is **plain HTTP with digest authentication**. That is acceptable on a trusted home LAN. Do not expose it to the internet.
- The AMT password is stored on the ESP32 in `secrets.h` (compiled into the firmware) and nowhere else in this repo. If you ever commit it by mistake, change the AMT password, not just the file.
- Consider a limited AMT user instead of `admin`.

## Limitations

- **Needs AMT hardware.** Most consumer PCs do not have it. On a desktop or mini PC with no battery, a relay or smart plug on the power feed is simpler and works on anything.
- **One machine, one real run.** Tested on a Dell Latitude 7480 (AMT 11.8.97) with a deliberate sysrq kernel crash. The server was back about 70 seconds after the reset command.
- **A reboot is recovery, not diagnosis.** After a hard cut there may be nothing useful in the previous boot's journal.
- **The ESP32 is a single point of failure** on Wi-Fi.
- **Hard cuts can lose unsaved data.** The 5-minute wait is deliberate, so a normal reboot or a slow write does not trigger a reset.
- It watches SSH on port 22 and DNS on port 53. If your server does not run both, change the probes.

## Files

```
esp32_amt_watchdog/
  esp32_amt_watchdog.ino   the sketch
  secrets.example.h        copy to secrets.h and fill in
examples/
  get-power-state.xml      read-only AMT request for testing
```

## License

No license has been chosen yet. Add a `LICENSE` file before reuse.
