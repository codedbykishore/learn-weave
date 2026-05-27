# make host — Public URL for LearnWeave

## What it does

`make host` starts all services and exposes them through a single public URL using ngrok.

```
Frontend (port 3000)  →  ngrok  →  https://xxxx.ngrok-free.dev
     ↕ proxy (/api)
Backend (port 8000)
```

Both frontend and backend are accessible through one URL because Vite's dev server proxies `/api` requests to the backend internally.

## Usage

```bash
make host      # Start everything + get public URL
make kill      # Stop everything
```

## Prerequisites

- `ngrok` installed and authenticated (`ngrok config add-authtoken <token>`)
- `backend/.env` configured
- `backend/venv` created (`make install-backend`)

## How it works

The Makefile target runs these steps:

1. **Kill old processes** on ports 3000, 8000, 4040
2. **Start backend** on port 8000 using `setsid` (detaches from terminal)
3. **Start frontend** on port 3000 using `setsid`
4. **Start ngrok** tunnel to port 3000 using `setsid`
5. **Print the public URL** fetched from ngrok's API at `http://127.0.0.1:4040`

`setsid` is critical — it puts each process in its own session so they survive after `make` exits.

## Traffic flow

```
Browser → https://ngrok.io/app/page        → Vite (3000) → serves frontend
Browser → https://ngrok.io/api/auth/login  → Vite (3000) → proxy → backend (8000)
```

## OAuth / Google Login — Why it broke and how it's fixed

### The problem

Google OAuth requires a **redirect URI** — the URL Google sends the user back to after they
consent. This URI must match exactly what's registered in Google Cloud Console.

In `.env`:
```
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
```

When ngrok gives a URL like `https://unveridic-hooded-flo.ngrok-free.dev`:

1. User clicks "Login with Google" on `https://ngrok.io`
2. Backend tells Google: "redirect back to `http://localhost:8000/api/auth/google/callback`"
3. Google sends the user to `http://localhost:8000` — not the ngrok URL
4. The browser navigates to localhost:8000. Session cookie (which stores OAuth state)
   was set on the ngrok domain, so it's lost → state validation fails
5. Error: "Could not validate credentials"

### The fix

The backend dynamically detects the public URL instead of using the hardcoded env var.

**Step 1 — Vite proxy forwards the original host:**

`frontend/vite.config.js` adds two custom headers to proxied requests:

| Header | Value | Example |
|--------|-------|---------|
| `X-Original-Host` | The browser's Host header | `unveridic-hooded-flo.ngrok-free.dev` |
| `X-Original-Proto` | `http` if host is localhost, else `https` | `https` |

This is done in the `proxyReq` event handler inside the `/api` proxy config.

**Step 2 — Backend uses these headers:**

`backend/src/api/routers/auth.py` — All three OAuth login endpoints (Google, GitHub, Discord)
read `X-Original-Host` and `X-Original-Proto` to build the redirect URI dynamically:

```python
original_host = request.headers.get("X-Original-Host")
if original_host:
    scheme = request.headers.get("X-Original-Proto", "https")
    redirect_uri = f"{scheme}://{original_host}/api/auth/google/callback"
else:
    redirect_uri = settings.GOOGLE_REDIRECT_URI  # fallback for local dev
```

**Step 3 — Post-login redirect uses the same headers:**

`backend/src/services/auth_service.py` — After successful OAuth, the redirect back to the
frontend also uses the dynamic host instead of the hardcoded `FRONTEND_BASE_URL` env var.

### End-to-end OAuth flow (working)

```
1. Browser:     GET https://ngrok.io/api/auth/login/google
2. Vite proxy:  forwards to http://127.0.0.1:8000/api/auth/login/google
                 adds X-Original-Host: ngrok.io
                 adds X-Original-Proto: https
3. Backend:     reads X-Original-Host → builds redirect_uri = https://ngrok.io/api/auth/google/callback
                 stores state in session cookie (domain: ngrok.io)
                 redirects 302 to Google consent with that redirect_uri
4. Browser:     follows redirect to Google, user consents
5. Google:      redirects back to https://ngrok.io/api/auth/google/callback
6. Browser:     sends session cookie (includes OAuth state)
7. Vite proxy:  forwards to backend with X-Original-Host header
8. Backend:     validates state from session cookie ✓
                 exchanges code for tokens
                 sets access_token + refresh_token cookies (domain: ngrok.io)
                 redirects to https://ngrok.io/ (using X-Original-Host)
9. User is logged in on the ngrok URL ✓
```

## Files changed

| File | Change |
|------|--------|
| `frontend/vite.config.js` | Added `allowedHosts: true` so tunnel hosts aren't blocked |
| `frontend/vite.config.js` | Added `X-Original-Host` and `X-Original-Proto` header forwarding in proxy |
| `backend/src/api/routers/auth.py` | Google/GitHub/Discord login endpoints use dynamic redirect URI from headers |
| `backend/src/services/auth_service.py` | OAuth callback redirect uses dynamic frontend URL from headers |
| `Makefile` | Added `host` and `kill` targets |

## The tunnel

ngrok free plan allows one tunnel at a time. The tunnel goes to the **frontend** (port 3000).
The frontend's Vite dev server proxies all `/api/*` requests to the backend (port 8000),
so the entire app works through a single URL.

- **App**: `https://<random>.ngrok-free.dev`
- **API**: `https://<random>.ngrok-free.dev/api/*`
- **Inspect**: `http://127.0.0.1:4040` (ngrok request inspector)

## Why not two tunnels?

Free ngrok = 1 tunnel. Other free options (localtunnel, serveo, bore) were unreliable —
kept dying in background or required browser interaction. The single-tunnel approach is
simpler and more stable.

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| `404` from ngrok URL | ngrok process died — run `make kill && make host` |
| `Could not validate credentials` | OAuth redirect/cookie domain mismatch — or stale `.env` values |
| Frontend loads, API calls fail | Backend not running — check `ss -tlnp \| grep 8000` |
| Google says "redirect_uri_mismatch" | Google Cloud Console has a different URI than what the backend sends |
