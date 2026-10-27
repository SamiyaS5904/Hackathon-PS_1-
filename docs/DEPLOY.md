# Deploying Timetabl.ai

**Web app on Vercel · backend + AI assistant on Fly.io (one always-on machine) · database on Supabase.**

```
 Browser ──► Vercel (Next.js web app)
               │  https://<app>.fly.dev/api/...         (data, timetable engine)
               │  https://<app>.fly.dev/assistant/...   (AI assistant, voice)
               ▼
   Fly.io machine (one Docker container, 1 GB RAM, Singapore)
     backend  :8080  ──passes /assistant/... to──►  assistant :8001 (inside the container only)
               │
               ▼
   Supabase Postgres (the same database you use locally)
```

**Cost:** Fly.io bills per second while the machine runs, with no plan or minimum. 1 GB shared CPU is about
**$5.70 a month** if left on all the time (about $0.19 a day). Stop it when you don't need it (step 6) and billing
stops. Claude and OpenAI usage is billed separately, on your own API keys. Total set-up time: about 20 minutes, most
of it the first build.

> **Important: one backend per database.** The backend keeps each college in memory and saves to Supabase in the
> background. Don't run the local app (`start-local.bat`) and the live site against the same database at the same
> time, or one can overwrite the other's changes. Close the local backend before step 3.

---

## 1. Install Fly.io and log in (5 minutes)

1. Sign up at **fly.io**, then add your card in **Dashboard → Billing**. The card must allow international payments.
2. Install the command-line tool in PowerShell:

   ```powershell
   iwr https://fly.io/install.ps1 -useb | iex
   ```

3. Close and reopen the terminal. Then log in (a browser window opens):

   ```powershell
   fly auth login
   ```

## 2. Create the app and its secrets (3 minutes)

In a terminal **at the project folder** (`D:\Hackathon`):

```powershell
fly apps create timetabl-api
```

If the name is taken, pick another one (for example `timetabl-api-samiya`) and put the same name in the first line of
`fly.toml` (`app = "..."`).

Copy the four secrets straight from your `.env` files. This prints nothing on screen:

```powershell
Get-Content backend\.env, chatbot\.env | Select-String '^(DATABASE_URL|APP_SECRET|ANTHROPIC_API_KEY|OPENAI_API_KEY)=' | ForEach-Object { $_.Line } | fly secrets import --stage
```

```powershell
fly secrets set --stage CORS_ORIGINS="http://localhost:3000"
```

`fly secrets list` shows the names (never the values). You should see five.

## 3. Deploy (8-10 minutes the first time)

```powershell
fly deploy --ha=false
```

`--ha=false` makes exactly **one** machine; the app needs that. The build runs on Fly's servers, so your laptop does
little work.

Check it:
- `https://timetabl-api.fly.dev/api/health` should answer `{"ok": true, ...}`. Use your app name in place of
  `timetabl-api`.
- `fly logs` shows the backend and assistant output.

The first start loads both demo colleges from Supabase. It can take a minute before the health check answers.

## 4. Web app on Vercel (5 minutes)

1. **vercel.com → Add New → Project → Import** your GitHub repository.
2. **Root Directory: `frontend`** (Framework: Next.js is detected).
3. **Environment Variables**:
   - `NEXT_PUBLIC_BACKEND_URL` = `https://timetabl-api.fly.dev`
   - `NEXT_PUBLIC_CHATBOT_URL` = `https://timetabl-api.fly.dev/assistant`
4. **Deploy**. Note the address, for example `https://timetabl-ai.vercel.app`.
5. Allow that address to call the API, and use it in invite links. The machine restarts by itself:

   ```powershell
   fly secrets set CORS_ORIGINS="https://timetabl-ai.vercel.app,http://localhost:3000" FRONTEND_URL="https://timetabl-ai.vercel.app"
   ```

## 5. Check the live site (3 minutes)

1. Open the Vercel address. You should see the home page. Click **Try the demo**, then **College Admin**.
2. Home shows the published timetable with 0 clashes. The **GNDEC** tab on the Demo page has the second college.
3. Press **Ctrl+K** and ask "Which rooms are free right now?". You should get an instant answer.
4. Ask "Dr. Harpreet Kaur is away tomorrow, plan cover". You should get the plan card.
5. Switch to **Talk**, allow the microphone and speak. It should answer aloud.

If something fails, check two places:
- `fly logs` shows the backend and assistant output.
- A `CORS` error in the browser console means step 4.5 is missing the exact Vercel address.

## 6. Day-to-day

| Task | Command |
|---|---|
| Update after a code change | `fly deploy --ha=false` |
| See what's happening | `fly logs` · `fly status` |
| **Stop it (billing stops)** | `fly scale count 0` |
| Start it again | `fly scale count 1` |
| More speed / memory (about 2x the cost) | `fly scale vm shared-cpu-2x --vm-memory 2048` |

Raise the machine size if either of these happens:
- the logs show "Out of memory",
- Generate is too slow for the demo.

## Settings reference

| Setting | Where | Meaning |
|---|---|---|
| `DATABASE_URL` | Fly secret | Supabase Postgres (empty = a local SQLite file inside the machine; lost on restart) |
| `APP_SECRET` | Fly secret | Signs login tokens. Keep it the same everywhere you share the database |
| `ANTHROPIC_API_KEY` | Fly secret | The assistant (Claude). Without it the rest of the app still works |
| `OPENAI_API_KEY` / `OPENROUTER_API_KEY` | Fly secret | Optional natural voice (listening + speaking) |
| `CORS_ORIGINS` | Fly secret | Web app addresses allowed to call the API, comma separated |
| `FRONTEND_URL` | Fly secret | The web app address used in invite links |
| `DEMO_PLATFORM_OWNER` | `fly.toml` (1) | `1` shows the platform owner demo login (`owner@demo.timetabl.ai`) |
| `SUPERADMIN_EMAILS` | Fly secret | Real platform owners, comma separated |
| `SOLVER_WORKERS` | `fly.toml` (1) | Parallel workers while generating; raise it with a bigger machine |
| `CHAT_MODEL` / `CHAT_FAST_MODEL` / `CHAT_RETRY_MODEL` | optional | Assistant models (default Sonnet 5.5 / Haiku 5.5 / Opus 5.5) |
| `NEXT_PUBLIC_BACKEND_URL` / `NEXT_PUBLIC_CHATBOT_URL` | Vercel | Where the web app finds the API and the assistant |

## Rules that keep it correct

- **One machine per database** (`--ha=false`, one backend process). College data lives in memory and is saved in
  the background.
- **Secrets only in Fly secrets and your local `.env` files.** `.dockerignore` keeps every `.env` file, local database
  and test out of the image.
- **The timetable is always made by the algorithm.** The AI assistant only prepares changes that people apply.

Other hosts: `deploy/hf-space/` (a Hugging Face Docker Space, now a paid plan) and `render.yaml` (Render) also work
with the same code.
