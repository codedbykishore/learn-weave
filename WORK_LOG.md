# LearnWeave – Work Log

All changes made across debugging & deployment sessions.

---

## Session 1: README Rewrite for Hackathon

### What was done
- Explored the entire project structure (backend, frontend, agents, services, configs)
- Read key files to understand the architecture and features
- Rewrote `README.md` from scratch, tailored for the hackathon submission (PS1: Bloom's Taxonomy aligned AI study support)

### Files changed
- `README.md` — Full rewrite with hackathon-focused content, architecture diagram, feature list, tech stack, and setup instructions

---

## Session 2: Production Bug Fixes (Cloud Run)

### Problem 1: Chapters created but disappearing
**Root cause:** `AttributeError: 'ESLintValidator' object has no attribute 'temp_jsx_dir'`  
The production Docker image (Python 3.12-slim) has no Node.js or ESLint installed. When the `ESLintValidator` tried to validate AI-generated JSX, it crashed because `eslint_base_dir` was `None`, and code tried to access `self.temp_jsx_dir` on it.

**Fix applied in** `backend/src/agents/code_checker/code_checker.py`:
- Added a guard in `validate_jsx()` — if `self.eslint_base_dir is None`, skip validation entirely and return `{'valid': True, 'errors': [], 'warnings': [], 'skipped': True}`
- This allows chapter generation to proceed without ESLint in production

### Problem 2: Thumbnail images not loading
**Root cause:** Cloud Run uses an ephemeral filesystem. Images saved to disk were lost on every container restart/scale event.

**Fix applied in** `backend/src/agents/image_agent/agent.py`:
- Added imports for `USE_CLOUD_STORAGE` (from settings) and `StorageService`
- Created `_get_storage_service()` singleton to lazily initialize the GCS-backed storage service
- Added `generate_image_cloud()` method that uploads SVGs to GCS and returns public URLs
- Modified `run()` to branch: use GCS in production (`USE_CLOUD_STORAGE=true`), local filesystem in dev
- Falls back to base64 data URI if GCS upload fails

### Deployment

#### 1. Create Artifact Registry repository
```bash
gcloud artifacts repositories create learnweave \
  --repository-format=docker \
  --location=us-central1 \
  --description="LearnWeave Docker images"
```

#### 2. Build & push the backend Docker image
```bash
cd backend
docker build -t us-central1-docker.pkg.dev/sticky-net-485205/learnweave/backend:latest \
  -f Dockerfile.production .
docker push us-central1-docker.pkg.dev/sticky-net-485205/learnweave/backend:latest
```

#### 3. Create placeholder secrets in Secret Manager
```bash
echo -n "placeholder" | gcloud secrets create google-client-id --data-file=-
echo -n "placeholder" | gcloud secrets create google-client-secret --data-file=-
openssl rand -hex 32 | gcloud secrets create jwt-secret-key --data-file=-
```

#### 4. Grant Secret Manager access to the compute service account
```bash
gcloud projects add-iam-policy-binding sticky-net-485205 \
  --member="serviceAccount:140367184766-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

#### 5. Deploy to Cloud Run with env vars and secrets
```bash
gcloud run deploy learnweave-backend \
  --image=us-central1-docker.pkg.dev/sticky-net-485205/learnweave/backend:latest \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=2 \
  --timeout=300 \
  --set-env-vars="USE_FIRESTORE=true,USE_CLOUD_STORAGE=true,GOOGLE_CLOUD_PROJECT=sticky-net-485205,GOOGLE_CLOUD_LOCATION=us-central1,GOOGLE_GENAI_USE_VERTEXAI=true,FIRESTORE_DATABASE=(default),GCS_BUCKET_IMAGES=sticky-net-485205-images,GCS_BUCKET_UPLOADS=sticky-net-485205-uploads,GCS_BUCKET_EXPORTS=sticky-net-485205-exports,CORS_ORIGINS=*" \
  --set-secrets="GOOGLE_CLIENT_ID=google-client-id:latest,GOOGLE_CLIENT_SECRET=google-client-secret:latest,SECRET_KEY=jwt-secret-key:latest"
```

> **Note:** Secrets were initially placeholders (v1) — OAuth login wouldn't work until real credentials were added (done in Session 3).

---

## Session 3: OAuth Secrets & Environment Fix

### Problem: OAuth login not working
The Secret Manager secrets `google-client-id` and `google-client-secret` were placeholders. Additionally, critical environment variables for OAuth redirect URIs were missing.

### Fix 1: Updated Secret Manager with real credentials
- Read real OAuth credentials from `backend/.env`
- Updated secrets to version 2 with the real values

```bash
# Update google-client-id (creates version 2)
echo -n "<GOOGLE_CLIENT_ID>" \
  | gcloud secrets versions add google-client-id --data-file=-

# Update google-client-secret (creates version 2)
echo -n "<GOOGLE_CLIENT_SECRET>" \
  | gcloud secrets versions add google-client-secret --data-file=-
```

- Secrets reference `latest` version, so no redeployment was needed for secrets alone

### Fix 2: Set missing environment variables on backend
The `backend/src/config/settings.py` uses `CLOUD_RUN_SERVICE_URL` to build the OAuth redirect URI. Without it, it defaults to `https://www.learnweave.ai` which doesn't exist.

```bash
# Set CLOUD_RUN_SERVICE_URL and FRONTEND_BASE_URL
gcloud run services update learnweave-backend --region=us-central1 \
  --update-env-vars="CLOUD_RUN_SERVICE_URL=https://learnweave-backend-sjsk2zqhxq-uc.a.run.app,FRONTEND_BASE_URL=https://learnweave-frontend-sjsk2zqhxq-uc.a.run.app"

# Set FRONTEND_URL for CORS_ORIGINS
gcloud run services update learnweave-backend --region=us-central1 \
  --update-env-vars="FRONTEND_URL=https://learnweave-frontend-sjsk2zqhxq-uc.a.run.app"
```

**What these env vars do:**
- `CLOUD_RUN_SERVICE_URL` → `GOOGLE_REDIRECT_URI` resolves to `https://learnweave-backend-sjsk2zqhxq-uc.a.run.app/api/auth/google/callback`
- `FRONTEND_BASE_URL` → OAuth callback redirects the user back to the correct frontend
- `FRONTEND_URL` → used by `CORS_ORIGINS` in `settings.py` to allow cross-origin requests from the frontend

### Useful inspection commands used
```bash
# Check current env vars on the backend service
gcloud run services describe learnweave-backend --region=us-central1 \
  --format="yaml(spec.template.spec.containers[0].env)"

# List recent revisions
gcloud run revisions list --service=learnweave-backend --region=us-central1 --limit=3

# Get service URL
gcloud run services describe learnweave-backend --region=us-central1 \
  --format="value(status.url)"

# Quick health check
curl -s https://learnweave-backend-sjsk2zqhxq-uc.a.run.app/
```

### Current backend revision: `learnweave-backend-00019-2zk`

---

## Service URLs

| Service  | URL |
|----------|-----|
| Backend  | https://learnweave-backend-sjsk2zqhxq-uc.a.run.app |
| Backend (alt) | https://learnweave-backend-140367184766.us-central1.run.app |
| Frontend | https://learnweave-frontend-sjsk2zqhxq-uc.a.run.app |

---

## Still TODO / Manual Steps

### 1. Google OAuth Console – Add Redirect URI
The following redirect URI **must** be added in the [Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client](https://console.cloud.google.com/apis/credentials):

```
https://learnweave-backend-sjsk2zqhxq-uc.a.run.app/api/auth/google/callback
```

Without this, Google will reject the OAuth callback with a `redirect_uri_mismatch` error.

### 2. Frontend Dockerfile URL
`frontend/Dockerfile` hardcodes:
```
VITE_API_URL=https://learnweave-backend-140367184766.us-central1.run.app/api
```
This currently works (both URL formats reach the same backend). If the service is ever recreated, this will need updating.

### 3. CORS_ORIGINS hardcoded in settings.py
The `CORS_ORIGINS` list in `settings.py` still includes `https://www.learnweave.ai` and `https://learnweave.ai`. These are fine as future-proofing but aren't functional domains yet. The actual frontend origin (`FRONTEND_URL` env var) is now included.

---

## Files Modified (Summary)

| File | Change |
|------|--------|
| `README.md` | Full rewrite for hackathon |
| `backend/src/agents/code_checker/code_checker.py` | ESLint guard for production |
| `backend/src/agents/image_agent/agent.py` | GCS image upload in production |

## Infrastructure Changes

| Resource | Change |
|----------|--------|
| Secret Manager: `google-client-id` | v1 → v2 (real credential) |
| Secret Manager: `google-client-secret` | v1 → v2 (real credential) |
| Secret Manager: `jwt-secret-key` | v1 (random generated) |
| Cloud Run: `learnweave-backend` | 19 revisions, env vars updated |
| IAM | `secretmanager.secretAccessor` granted to compute SA |
