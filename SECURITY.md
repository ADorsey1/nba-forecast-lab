# Security Notes

## Current Scope

NBA Forecast Lab is a local Streamlit application that reads public basketball data and writes local forecast artifacts. It is a public read-only dashboard with no user database, payment flow, file upload, or private-user-data surface. The app does not read legacy local login secrets.

## Controls Implemented

- Secret-bearing files are ignored by default, including `.env`, key files, certificate files, `secrets/`, and generated logs.
- `scripts/security_audit.py` scans project text files for common API keys, tokens, passwords, bearer credentials, and private-key blocks without printing matched secret values.
- The cookie notice records dismissal only in the current Streamlit session; it does not set an advertising or analytics cookie.
- UTM parameters are retained only in the current session for diagnostics and are not sent to an analytics provider.
- Raw HTML rendering is limited to static layout plus escaped values from data files.
- Live JSON and HTML provider responses have size limits and request timeouts to reduce resource-exhaustion risk.
- Streamlit XSRF protection is enabled, usage statistics are disabled, upload size is capped, and user-facing errors are reduced to error types.
- The local server binds to loopback by default so the development process is not exposed to the LAN or internet.
- Data-contract checks validate team grain, roster keys, forecast completeness, and live artifact availability.
- Dependencies are checked with `pip check`; use `pip-audit` before publishing a deployment.

Run the local checks with:

```powershell
$env:PYTHONPATH = "src"
& ".venv\Scripts\python.exe" scripts\security_audit.py
& ".venv\Scripts\python.exe" -m pip check
& ".venv\Scripts\python.exe" -m pytest -q
```

## Not Applicable Locally

Database row-level security, parameterized SQL, bot protection, encrypted sensitive records, and upload validation are not implemented because this application does not expose those surfaces. If a database, multi-user account system, or upload feature is added, those controls become mandatory before release.

## Hosted Deployment Requirements

Host the public read-only dashboard behind managed HTTPS. Keep secrets and refresh credentials in the host secret store, restrict raw provider payloads and logs to operators, and run dependency scanning in CI. Refresh jobs must run separately from web requests. The local loopback server is for development. If private user features are added later, use managed identity and server-side authorization before exposing those features; the legacy single-account helpers are not a production identity system.
