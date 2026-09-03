# Security Notes

## Current Scope

NBA Forecast Lab is a local Streamlit application that reads public basketball data and writes local forecast artifacts. It has a lightweight single-account login gate backed by Streamlit secrets, but no user database, payment flow, file upload, or private-user-data surface.

## Controls Implemented

- Secret-bearing files are ignored by default, including `.env`, key files, certificate files, `secrets/`, and generated logs.
- `scripts/security_audit.py` scans project text files for common API keys, tokens, passwords, bearer credentials, and private-key blocks without printing matched secret values.
- Passwords are stored as salted PBKDF2-SHA256 hashes, not plaintext values.
- Login sessions use a sliding expiration window and per-session failure throttling.
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

The development server is not an internet-facing security boundary. The built-in gate protects the Streamlit session but is not a full identity provider or organization-wide access-control system. A public deployment must add server-side authentication or an OIDC provider, HTTPS termination, security headers at a reverse proxy, origin allowlisting, distributed rate limiting, dependency scanning in CI, secret management through the host, and restricted access to raw live-provider payloads and logs. Do not expose the local Streamlit process directly to the public internet.
