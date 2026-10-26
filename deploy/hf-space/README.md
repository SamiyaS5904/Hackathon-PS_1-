---
title: Timetabl.ai API
emoji: 📅
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Backend and AI assistant for Timetabl.ai
---

# Timetabl.ai: backend + assistant

Clash-free college timetables. This Space runs the API (timetable engine, validator, data) and the AI assistant;
the web app runs on Vercel and talks to it.

- API: `/api/...` (health: `/api/health`)
- Assistant: `/assistant/...` (chat, voice)

Settings live in this Space's **Settings → Variables and secrets** (never in the code).
