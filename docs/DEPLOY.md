# Deploying Timetabl.ai (V1)

| Piece | Where | Cost |
|---|---|---|
| Web app (`frontend/`) | **Vercel** | free |
| Backend API (`backend/`) | **Railway** | ~$5/month, usage based (trial credit to start) |
| Assistant (`chatbot/`) | **Railway** (same project) | included above |
| Database | **Supabase** (already set up) | free |

Secrets are typed into each dashboard. Never put them in the repository or in chat.
After this, every push to `main` on GitHub redeploys automatically.

## 0. Two things from Supabase (5 minutes)

1. **Region**: Supabase → Project Settings → General → *Region*. You'll pick the nearest Railway
   region in step 1 (for India: **Singapore**, `asia-southeast1`).
2. **Session pooler URL** (cloud servers use IPv4, so the "Direct" URL won't work there):
   Supabase → **Connect** → *Direct · Connection string* → Method **Session pooler** → copy.
   It contains `pooler.supabase.com`. Replace `[YOUR-PASSWORD]` with your database password.

## 1. Backend + assistant on Railway (10 minutes)

1. railway.com → **Login with GitHub** → allow access to the `Hackathon-PS_1-` repository.
2. **New Project → Deploy from GitHub repo** → pick the repository. This creates the first service.
3. Open that service → **Settings**:
   - *Source → Root Directory*: `backend`
   - *Deploy → Region*: Singapore (or the one nearest your Supabase region)
   - *Networking → Generate Domain* → you get e.g. `https://backend-production-xxxx.up.railway.app`
4. Same service → **Variables**:

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the Session pooler URL from step 0 |
   | `APP_SECRET` | a long random string (run `python -c "import secrets; print(secrets.token_urlsafe(48))"`) |
   | `CORS_ORIGINS` | `http://localhost:3000` for now (the Vercel URL is added in step 3) |
   | `FRONTEND_URL` | same as `CORS_ORIGINS` |

5. In the project: **+ New → GitHub Repo** → the same repository again (second service):
   - *Root Directory*: `chatbot`, same region, **Generate Domain**
   - **Variables**: `ANTHROPIC_API_KEY` = your Claude key, `BACKEND_URL` = the backend domain from 3,
     `CORS_ORIGINS` = same as the backend.
6. Both deploy by themselves (start commands and health checks come from `railway.toml` in each
   folder). If a deploy log says it doesn't know how to start the app, set it by hand in
   *Settings → Deploy → Custom Start Command*:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
   (or *Settings → Config-as-code* → `backend/railway.toml` / `chatbot/railway.toml`). Then check in the browser:
   - `<backend domain>/api/health` → `{"ok":true}` (the first start also loads the demo college: ~30 s)
   - `<assistant domain>/health` → `"assistant_configured":true`

## 2. Web app on Vercel (5 minutes)

1. vercel.com → **Continue with GitHub** → **Add New → Project** → import the repository.
2. **Root Directory**: `frontend` (Next.js is detected).
3. **Environment Variables**:
   - `NEXT_PUBLIC_BACKEND_URL` = the backend domain (no `/` at the end)
   - `NEXT_PUBLIC_CHATBOT_URL` = the assistant domain
4. **Deploy** → you get `https://<name>.vercel.app`.

## 3. Connect them

On Railway, set `CORS_ORIGINS` and `FRONTEND_URL` of **both** services to the Vercel URL. Several
are allowed, comma-separated: `https://<name>.vercel.app,http://localhost:3000`. Railway redeploys.

## 4. Check the live site

1. Open the Vercel URL → **College Admin** demo login (password `demo1234`).
2. Dashboard: 0 clashes and a quality score. Timetable: drag a class → review → Apply → Undo.
3. **Student** demo login → only CSE-3A's classes. Press **Ctrl+K** → "What do I have tomorrow?".

## Rules that keep it correct

- **One instance per service** (Railway's default; don't raise *Replicas*). Data is kept in memory and
  saved to Supabase in the background, in order; two instances would not see each other's changes.
- Open the site a few minutes before presenting.
- Change secrets in the dashboards, never in code.

`render.yaml` is kept as an alternative (Render instead of Railway); you only need one of them.
