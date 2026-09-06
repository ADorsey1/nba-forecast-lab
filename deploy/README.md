# Hosting and refresh

Run the public Streamlit dashboard behind managed HTTPS with WebSocket support. This repository does not create a cloud account or activate a hosted job automatically.

Use Python 3.12. Install dependencies into `.venv`. The app entry point is `app/streamlit_app.py`. A container/reverse-proxy deployment must override the local loopback default with `--server.address 0.0.0.0`; expose it only through the HTTPS proxy.

Refresh separately using:

```sh
.venv/bin/python scripts/refresh_forecast.py --check
.venv/bin/python scripts/refresh_forecast.py --data-root /var/lib/nba-forecast
```

Keep `/var/lib/nba-forecast` on a persistent volume and set `NBA_FORECAST_DATA_ROOT` to the same path for the app and refresh worker. Retain this volume across releases and back it up. The web process needs read access only; the refresh worker needs write access. The historical source must be installed before refresh.

The included systemd units are templates for a Linux host using `/opt/nba-forecast-lab` and an `nba-forecast` service account. Adjust paths/user, provision the persistent directory, copy units into `/etc/systemd/system`, then enable `nba-forecast-refresh.timer`. It runs every six hours and catches up after downtime. systemd prevents overlapping instances of this service. Configure monitoring to alert on the failed unit or `refresh_status.json` with `status=failed`; the failure unit emits an error to the system journal. No external notification destination is configured by this repository.

Verify on the target host before launch: input check passes, manual refresh exits zero, timer is active, HTTPS/WebSockets work, a deliberately failed job triggers your monitoring, and web restarts retain published data. These checks require the actual hosting environment.

Refresh writes each complete dataset to `releases/<generation>/processed` and `releases/<generation>/raw/live`, validates it, then atomically replaces `current.json`. The web app reads that pointer once per render. Failed builds do not change it. Existing bundled `data/processed` and `data/raw/live` are used until the first successful publication. Keep published generations immutable. Retention is deliberately manual: keep the current generation, archived forecasts needed for evaluation, and any previous generation still in use; do not prune during an active web session. The CLI output path must end in `processed`.

The dashboard reloads every 15 minutes so an open browser session observes a newly published generation. This reload reads local published artifacts; it does not call live providers from a web request. The six-hour job remains the source of new data.
