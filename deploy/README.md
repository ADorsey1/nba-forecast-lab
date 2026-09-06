# Hosting and refresh

## Default: Community Cloud with GitHub refresh

The web app serves the committed portable snapshot, including Creative Lab ratings. It needs no historical checkout, writable volume, or in-process scheduler.

1. Push this repository to GitHub and enable Actions. The refresh workflow needs permission to write repository contents; branch protection must allow its snapshot commits.
2. Run **Refresh published snapshot** manually in Actions. Confirm it completes and commits a new bundle before relying on its six-hour schedule.
3. In Streamlit Community Cloud, create an app from this repository and branch, with entry point `app/streamlit_app.py` and Python 3.12. Dependencies come from `requirements.txt`. No login secrets are required.
4. Confirm Forecast provenance, live timestamps, and a nonzero Creative Lab scenario delta at the public URL.

The workflow trains on the pinned history, validates a release, exports only portable artifacts, runs tests, and commits the bundle. Push conflicts fail safely instead of overwriting another commit. Check failed workflow runs and rerun after resolving the conflict. GitHub schedules may be delayed and can be disabled after repository inactivity; six hours is an attempted cadence, not an uptime guarantee. The 24-hour stale indicator remains truthful.

Sources: [Streamlit deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Optional: Linux VM with persistent storage

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

The dashboard checks for a new generation every minute outside Creative Lab. This check reads local published artifacts; it does not call live providers from a web request. The six-hour job remains the source of new data.
