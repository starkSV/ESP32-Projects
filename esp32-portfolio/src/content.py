# All site copy lives here. Edit this file, then run: python build.py
#
# NOTE: the project case-study text below was gathered from shekharvaidya.in by a
# summarising fetch, so treat it as a close paraphrase, not your verbatim copy.
# Paste your exact wording over any field you want identical to the main site.

UTM = "?utm_source=Shekhar&utm_medium=portfolio&utm_campaign=featured-articles"

# Order matches shekharvaidya.in/projects (and its prev/next chain).
PROJECTS = [
    {
        "slug": "fps-calculator", "name": "FPS Calculator", "status": "live", "year": "2025",
        "tagline": "Predicts real-world gaming FPS for any CPU + GPU combo across 50+ titles.",
        "summary": "Backend on PostgreSQL with migrations, a localized React frontend, Docker deployment, and automated pytest runs on GitHub Actions.",
        "live": "https://fps.tech-latest.com", "source": "https://github.com/starkSV/fps-calculator",
        "stats": [("50", "AAA titles"), ("5", "Languages"), ("3", "Resolutions"), ("3", "Upscalers modeled")],
        "stack": ["FastAPI", "Python", "PostgreSQL", "React 19", "Tailwind CSS", "Docker", "Nginx"],
        "problem": "A yes/no “will my PC run this” check isn’t very useful, because the CPU/GPU balance changes by game, resolution, and upscaler.",
        "approach": "A calibrated frame-time model that splits each game’s frame time between CPU and GPU work using a per-game CPU fraction, then applies resolution, preset, and DLSS/FSR/XeSS adjustments.",
        "catch": "The hardware scoring has to match its sibling site, Bottleneck Calculator, since both read the same benchmark API.",
        "highlights": [
            "Per-game CPU fraction instead of a genre default",
            "VRAM penalty modeling for VRAM-limited cases",
            "Content written for AI search citation as well as Google",
            "Admin dashboard for game management, usage analytics, and CSV export",
        ],
    },
    {
        "slug": "msdl", "name": "MSDL", "status": "live", "year": "2026", "featured": True,
        "tagline": "Get official Windows ISOs directly from Microsoft's CDN — no account, no MCT.",
        "summary": "An open-source tool for getting official Windows ISO files from Microsoft's CDN without an account or the Media Creation Tool. It supports 38 languages and ARM64, x64, and x86. The frontend is React 19, TypeScript, and Tailwind v4; the backend is Go 1.22 on net/http with RWMutex-cached session parsing, running on a VPS over direct HTTP.",
        "live": "https://msdl.tech-latest.com", "source": "https://github.com/starkSV/windows-iso-downloader",
        "stats": [("1000s → ~75", "MS calls / day"), ("4", "Cache layers"), ("5", "Install channels"), ("38", "Languages")],
        "stack": ["Go", "React 19", "TypeScript", "Tailwind CSS v4", "Framer Motion"],
        "problem": "Microsoft requires an account and the Windows-only Media Creation Tool to download ISOs, which leaves out Linux, macOS, and IT admins who script rollouts.",
        "approach": "Reverse-engineers the session-registration flow used by Rufus’s Fido.ps1 and rebuilds it as a stateless Go proxy that any platform can call.",
        "catch": "At real traffic volume, Microsoft returns error 715-123130 and blocks the calling IP, so the caching architecture exists to scale without overloading Microsoft’s servers.",
        "highlights": [
            "A 4-layer cache (SKUs, signed links, eval redirects, negative results) with jittered TTLs",
            "singleflight collapses 500 concurrent cache misses into one outbound Microsoft call",
            "The CLI sends fetches back to warm the cache the website reads from",
            "Distributed as a web app and CLI through winget, Homebrew, a curl installer, raw binaries, and Termux/Android",
        ],
    },
    {
        "slug": "pixlyzer", "name": "Pixlyzer", "status": "live", "year": None, "featured": True,
        "tagline": "Professional media suite — image tools, PDF manipulation, and AI upscaling.",
        "summary": "A React frontend and FastAPI backend, with AI upscaling via Real-ESRGAN and background removal via Rembg running on cloud GPUs through Replicate. A companion React Native mobile app and an AMOLED dark theme round it out.",
        "live": "https://pixlyzer.com", "source": "https://github.com/starkSV/pixlyzer-v2",
        "stats": [("18", "Tools"), ("2", "Processing modes"), ("4x", "AI upscale"), ("3", "HEIC decode fallbacks")],
        "stack": ["FastAPI", "Python", "React", "React Native", "Replicate AI", "SQLite"],
        "problem": "Many “free” online image and PDF tools upload every file to a server, even for simple tasks, which exposes private files.",
        "approach": "A dual-mode engine: browser-based WASM processing (mupdf, jSquash, libheif) by default, with the FastAPI backend handling only operations that have no browser equivalent, such as LibreOffice conversions and GPU-based AI models.",
        "catch": "HEIC decoding uses three fallback stages: native createImageBitmap, then libheif-js WASM for 10-bit/HDR, then heic2any.",
        "highlights": [
            "18 tools, with uploads only when a server is genuinely needed",
            "4x AI upscaling and background removal on cloud GPUs",
            "Claude-generated alt text with 5 tone presets",
            "Companion React Native mobile app and an AMOLED dark theme with custom Tailwind tokens",
        ],
    },
    {
        "slug": "bottleneck-calculator", "name": "Bottleneck Calculator", "status": "live", "year": None, "featured": True,
        "tagline": "Visualise CPU/GPU bottlenecks and get upgrade suggestions for balanced PC builds.",
        "summary": "A web tool that analyses CPU/GPU pairings, computes bottleneck percentages, and recommends balanced upgrades, with a React frontend and a FastAPI backend serving calibrated benchmark datasets.",
        "live": "https://bottleneck.tech-latest.com", "source": "https://github.com/starkSV/bottleneck-calc",
        "stats": [("1,434", "CPUs scored"), ("0–10000", "Score scale"), ("S–D", "Tiers"), ("85%", "Cinebench data imputed")],
        "stack": ["React", "Vite", "Tailwind CSS", "FastAPI", "Python"],
        "problem": "Min-max normalized scores broke whenever a new flagship GPU such as the RTX 5090 was added: its outlier score shifted the ranks of every other card.",
        "approach": "Switched to percentile-based ranking, which absorbs new outliers without reshuffling existing scores, plus geometric-mean weighting across benchmark sources so a component has to perform consistently rather than spike in one test.",
        "catch": "Percentile scores preserve rank but not ratios, which produced unrealistic FPS predictions (about 350 FPS in Valorant for a GTX 1060). A separate ratio-preserving raw score is exposed for FPS Calculator’s math.",
        "highlights": [
            "1,434 CPUs scored, with about 85% of missing Cinebench data imputed by regression (R² ≈ 0.90)",
            "Percentile normalization that stays stable when new hardware is added",
            "One shared scoring engine powers both this tool and FPS Calculator",
            "Upgrade suggestions tuned by resolution and workload (gaming, productivity, or overall)",
        ],
    },
    {
        "slug": "minxlink", "name": "Minxlink", "status": "live", "year": "2026",
        "tagline": "Multi-tenant URL shortener with geo-routing, A/B testing, and custom domains.",
        "summary": "An advanced URL shortener with Clerk-based multi-tenancy, per-workspace custom domains, geo and device routing, A/B splits, and Cloudflare Workers KV for fast redirects. Built for marketing teams that need click-level attribution.",
        "live": "https://minxl.ink", "source": "https://github.com/starkSV/minxlink-v2",
        "stats": [("6+", "Redirect policies"), ("3", "Variant dimensions"), ("4", "Independent services")],
        "stack": ["FastAPI", "PostgreSQL", "Redis", "Cloudflare Workers", "React", "Clerk"],
        "problem": "Marketing teams need branded short links with real targeting, but most shorteners are simple slug-to-URL maps with no policy layer.",
        "approach": "Policy logic runs at the edge: a Cloudflare Worker handles geo, device, and A/B variant resolution, plus scheduling, password gates, click limits, and blocked IPs, and renders interstitial and social-preview pages before requests reach the backend.",
        "catch": "Caching redirect decisions at the edge means invalidation has to be exact: a stale cached variant sends the wrong audience to the wrong link until the cache expires or is purged.",
        "highlights": [
            "The edge worker enforces runtime policy: scheduling, password gates, click limits, blocked IPs, deep linking, and interstitials",
            "Each link can have geo, device, and A/B redirect variants",
            "Social previews unfurl correctly on Slack, Twitter, and similar platforms",
            "Multi-tenancy with Clerk and custom domains per workspace",
        ],
    },
    {
        "slug": "skysift", "name": "SkySift", "status": "wip", "year": "2025",
        "tagline": "India-focused aviation intelligence — live flight tracking, price discovery, AI route insights.",
        "summary": "A real-time aviation platform for the Indian market. It pulls live data from the OpenSky Network, processes it with FastAPI, PostgreSQL, and Redis, shows it on Mapbox GL maps, and gets route insights from the Claude API. Deployed with Docker Compose on Coolify.",
        "live": "https://skysift.in", "source": "https://github.com/starkSV/skysift",
        "stats": [("60s", "Refresh interval"), ("6", "Containers"), ("7 days", "Insight window"), ("4", "Background jobs")],
        "stack": ["FastAPI", "Python", "Mapbox GL", "React", "TypeScript", "Claude API", "Redis"],
        "problem": "Standard flight trackers show aircraft positions on a map but don’t explain whether a route is usually busy, which airline dominates it, or when traffic is quiet.",
        "approach": "A 60-second OpenSky polling loop, plus background workers that enrich every visible flight rather than only the ones a user clicks. A daily Claude job then writes a narrative for each route from seven days of history.",
        "catch": "Insights need accumulated history to be reliable, so the product is deliberately quiet on day one.",
        "highlights": [
            "Proactive enrichment through background workers instead of click-triggered lookups",
            "AI-generated route narratives covering frequency, top airlines, and peak hour",
            "India-focused bounding box, designed to extend globally",
            "Six-container Docker Compose stack: api, poller, cron, frontend, postgres, redis",
        ],
    },
    {
        "slug": "win-perf-mon", "name": "WinPerfMon", "status": "wip", "year": "2025",
        "tagline": "One app to replace Task Manager, HWiNFO, GPU-Z, and Wireshark on Windows.",
        "summary": "A native Windows performance monitor that combines CPU, GPU, RAM, disk, and network metrics in one dark-themed WinUI 3 app, using LibreHardwareMonitor and LiveChartsCore with a SQLite ring buffer holding up to 30 days of history.",
        "live": "https://winperfmon.app", "source": "https://github.com/starkSV/win-perf-mon",
        "stats": [("5", "Tools replaced"), ("1s", "Sensor poll rate"), ("30 days", "History retention"), ("WinUI 3", "Platform")],
        "stack": ["C#", ".NET", "WinUI 3", "LibreHardwareMonitor", "SQLite", "LiveChartsCore"],
        "problem": "Diagnosing a Windows performance issue means juggling Task Manager, HWiNFO, GPU-Z, Wireshark, and Resource Monitor: five tools with five separate mental models.",
        "approach": "The app is split in two. An elevated Collector process polls hardware sensors, process state, and network activity every second and writes to a SQLite ring buffer. The WinUI 3 frontend reads live and historical data from that store, so the UI never blocks on sensor I/O.",
        "catch": "Deep hardware, process, and network data needs admin elevation, which forces the Collector to run as a separate elevated process the UI talks to, rather than inside the app.",
        "highlights": [
            "Consolidates Task Manager, HWiNFO, GPU-Z, Wireshark, and Resource Monitor into one app",
            "Per-subsystem accent colors (CPU, GPU, RAM, Network, Storage) with a shared health scale",
            "SQLite ring buffer with configurable retention up to 30 days",
            "Status: Processes is complete; Dashboard, Hardware, and Network sections are next",
        ],
    },
]

ARTICLES = [
    ("XDA", "I dumped 650K DNS records into Gemma, and it found patterns my dashboard completely missed",
     "Every device has something to hide.",
     "https://www.xda-developers.com/i-dumped-650k-dns-records-into-gemma-and-it-found-patterns-my-dashboard-completely-missed/"),
    ("XDA", "I replaced 6 paid subscriptions with a homelab on an old laptop — here's the full stack",
     "One laptop. Six bills. Zero regrets.",
     "https://www.xda-developers.com/i-replaced-6-paid-subscriptions-with-homelab-on-old-laptop/"),
    ("TechLatest", "Here's How I Keep My Remote Work Setup Secure",
     "Cybersecurity isn’t about products. It’s about habits.",
     "https://tech-latest.com/heres-how-i-keep-my-remote-work-setup-secure/"),
    ("XDA", "I replaced Tailscale with raw WireGuard for a month, and here's what I learned",
     "WireGuard didn’t fail me. My assumptions did.",
     "https://www.xda-developers.com/replaced-tailscale-with-raw-wireguard-for-month-heres-what-i-learned/"),
    ("TechLatest", "I Tested the Native Windows 11 Live Wallpaper Feature",
     "Windows 11 is finally getting native live wallpapers — but should you use them?",
     "https://tech-latest.com/i-tested-the-native-windows-11-live-wallpaper-feature/"),
    ("TechLatest", "How to Get Free Extended Security Updates (ESU) After Windows 10 End of Support",
     "Windows 10 support officially ended — but you can still get security updates for free.",
     "https://tech-latest.com/get-free-extended-security-updates-after-windows-10-end-of-support/"),
]

EXPERIENCE = [
    ("XDA", "Computing Writer", "Jan 2026–now"),
    ("TechLatest", "Founder & Editor", "6+ yrs"),
    ("eSportsLatest", "Founder", "6+ yrs"),
    ("GetDroidTips", "Tech Writer", "2020–2022"),
]

SKILLS = ["Python", "FastAPI", "Go", "React", "Next.js", "TypeScript", "Tailwind",
          "PostgreSQL", "Redis", "Cloudflare", "Docker"]

STATS = [("300K+", "Monthly readers"), ("8+", "Years writing"), ("3+", "Years building"), ("5+", "Live projects")]

MARQUEE = ["Let's build together", "Available for freelance", "Open to collaborations", "Full-stack development"]

EMAIL_USER, EMAIL_HOST = "shekhar", "techlatest.in"
RESUME = "https://shekharvaidya.in/assets/shekhar-resume-2026.pdf"
