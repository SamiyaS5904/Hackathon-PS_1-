# Deploying Timetabl.ai

**Web app on Vercel · backend + AI assistant on a Hugging Face Space (Docker) · database on Supabase.** All free tiers.

```
 Browser ──► Vercel (Next.js web app)
               │  https://<you>-timetabl-api.hf.space/api/...         (data, timetable engine)
               │  https://<you>-timetabl-api.hf.space/assistant/...   (AI assistant, voice)
               ▼
   Hugging Face Space (one Docker container, 16 GB RAM, 2 CPUs)
     backend  :7860  ──passes /assistant/... to──►  assistant :8001 (inside the container only)
               │
               ▼
   Supabase Postgres (the same database you use locally)
```

Why a Space: the timetable engine needs memory while it generates; the free Space has 16 GB, and it only sleeps
after 48 hours without visits. Total time: about 25 minutes, most of it waiting for builds.

> **Important: one backend per database.** The backend keeps each college in memory and saves to Supabase in the
> background. Don't run the local app (`start-local.bat`) and the live site against the same database at the same
> time, or one can overwrite the other's changes. For the demo, use the live site only (or the local one only).

---

## 0. Collect the settings (2 minutes)

From your own `backend/.env` and `chatbot/.env` (open them in Notepad; never paste them into chats or code):

| Setting | Where it comes from |
|---|---|
| `DATABASE_URL` | `backend/.env` (Supabase → Connect → Session pooler URI) |
| `APP_SECRET` | `backend/.env`. Use the **same** value, so existing logins keep working |
| `ANTHROPIC_API_KEY` | `chatbot/.env` |
| `OPENAI_API_KEY` | `chatbot/.env` (optional: natural voice; without it the browser's voice is used) |

## 1. Create the Space (5 minutes)

1. Go to **huggingface.co → New → Space**.
   - Owner: you. Space name: `timetabl-api`.
   - SDK: **Docker**, template **Blank**.
   - Hardware: **CPU basic (free)**.
   - Visibility: **Public**. The web app must be able to reach it; your data stays protected by the logins.
2. In the Space, open **Settings → Variables and secrets**:
   - **New secret** for each of: `DATABASE_URL`, `APP_SECRET`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`.
   - **New variable**:
     - `DEMO_PLATFORM_OWNER` = `1` (shows the platform owner demo login).
     - `CORS_ORIGINS` = `http://localhost:3000` for now. You'll add the Vercel address in step 3.
3. Create a **write token**: your profile → **Settings → Access Tokens → New token**, role **Write**. You'll type it
   as the password when pushing.

## 2. Push the code to the Space (10 minutes, mostly the build)

In a terminal at the project folder:

```bash
python deploy/make_hf_space.py
```

This builds `deploy/_hf_space/` (backend + assistant code, Dockerfile, start script). It never includes `.env`
files. Then push it:

```bash
cd deploy/_hf_space
git init -b main
git remote add origin https://huggingface.co/spaces/<your-username>/timetabl-api
git add .
git commit -m "Deploy Timetabl.ai"
git push -f origin main
```

When git asks: username = your Hugging Face username, password = the **write token** from step 1.

The Space shows **Building**, then **Running** (5-8 minutes the first time). Then check that it's up:
`https://<your-username>-timetabl-api.hf.space/api/health` should answer `{"ok": true, ...}`.

To update it later: run `python deploy/make_hf_space.py` again. Then in `deploy/_hf_space`, run
`git add . && git commit -m "Update" && git push`.

## 3. Web app on Vercel (5 minutes)

1. **vercel.com → Add New → Project → Import** your GitHub repository.
2. **Root Directory: `frontend`** (Framework: Next.js is detected).
3. **Environment Variables**:
   - `NEXT_PUBLIC_BACKEND_URL` = `https://<your-username>-timetabl-api.hf.space`
   - `NEXT_PUBLIC_CHATBOT_URL` = `https://<your-username>-timetabl-api.hf.space/assistant`
4. **Deploy**. Note the address, e.g. `https://timetabl-ai.vercel.app`.
5. Back in the Space, change the variable `CORS_ORIGINS` to:
   `https://timetabl-ai.vercel.app,http://localhost:3000`. The Space restarts by itself.

## 4. Check the live site (3 minutes)

1. Open the Vercel address. You should see the home page. Click **Try the demo**, then **College Admin**.
2. Home shows the published timetable with 0 clashes.
3. Press **Ctrl+K**, ask "Which rooms are free right now?". You should get an instant answer.
4. Ask "Dr. Harpreet Kaur is away tomorrow, plan cover". You should get the plan card.
5. Switch to **Talk**, allow the microphone and speak. It should answer aloud.

If something fails: the Space's **Logs** tab shows the backend and assistant output. A `CORS` error in the browser
console means step 3.5 is missing the exact Vercel address.

## Settings reference

| Setting | Where | Meaning |
|---|---|---|
| `DATABASE_URL` | Space secret | Supabase Postgres (empty = a local SQLite file) |
| `APP_SECRET` | Space secret | Signs login tokens. Keep it the same everywhere you share the database |
| `ANTHROPIC_API_KEY` | Space secret | The assistant (Claude). Without it the rest of the app still works |
| `OPENAI_API_KEY` / `OPENROUTER_API_KEY` | Space secret | Optional natural voice (listening + speaking) |
| `CORS_ORIGINS` | Space variable | Web app addresses allowed to call the API, comma separated |
| `DEMO_PLATFORM_OWNER` | Space variable | `1` shows the platform owner demo login (`owner@demo.timetabl.ai`) |
| `SUPERADMIN_EMAILS` | Space variable | Real platform owners, comma separated |
| `SOLVER_WORKERS` | Dockerfile (4) | Parallel workers while generating; lower it on small machines |
| `CHAT_MODEL` / `CHAT_FAST_MODEL` / `CHAT_RETRY_MODEL` | optional | Assistant models (default Sonnet 5.5 / Haiku 5.5 / Opus 5.5) |
| `NEXT_PUBLIC_BACKEND_URL` / `NEXT_PUBLIC_CHATBOT_URL` | Vercel | Where the web app finds the API and the assistant |

## Rules that keep it correct

- **One backend process per database** (the Dockerfile starts one). College data lives in memory and is saved in
  the background.
- **Secrets only in the Space settings and your local `.env` files.** `make_hf_space.py` refuses to build if a
  `.env` file would be included.
- **The timetable is always made by the algorithm.** The AI assistant only prepares changes that people apply.
