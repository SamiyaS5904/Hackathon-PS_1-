"""The web app's addresses are allowed by list or by pattern (every Vercel deployment of the project)."""

import importlib

from fastapi.testclient import TestClient


def test_origin_pattern_allows_project_deployments_only(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("CORS_ORIGIN_REGEX", r"^https://(hackathon-ps-1|timetabl-ai)[a-z0-9-]*\.vercel\.app$")
    import app.core.config as config
    import app.main as main
    importlib.reload(config)
    importlib.reload(main)
    try:
        client = TestClient(main.app)
        def allowed(origin: str) -> str | None:
            r = client.options("/api/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
            return r.headers.get("access-control-allow-origin")
        assert allowed("https://hackathon-ps-1.vercel.app") == "https://hackathon-ps-1.vercel.app"
        assert allowed("https://timetabl-ai-git-main-x.vercel.app") is not None
        assert allowed("http://localhost:3000") == "http://localhost:3000"
        assert allowed("https://evil.vercel.app") is None
    finally:
        monkeypatch.delenv("CORS_ORIGIN_REGEX")
        importlib.reload(config)
        importlib.reload(main)
