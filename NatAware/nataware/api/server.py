"""One process serving the built web app and the API (for demos).

    cd web && npm run build && cd ..
    uvicorn nataware.api.server:app

The API is mounted at /api (the same paths the Vite dev server proxies), and the web app
at /. During development run `uvicorn nataware.api.main:app --reload` and `npm run dev`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from nataware.api.main import app as api_app
from nataware.config import REPO_ROOT
from nataware.worker import tasks

DIST = REPO_ROOT / "web" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    tasks.bootstrap()  # mounted sub-apps don't run their own lifespan
    yield


app = FastAPI(title="NatAware", lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/api", api_app)

if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = DIST / path
        if path and candidate.is_file() and DIST in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def not_built() -> HTMLResponse:
        return HTMLResponse("<p>The web app isn't built yet. Run <code>npm run build</code> in <code>web/</code>, "
                            "or use the dev server (<code>npm run dev</code>). API docs: <a href='/api/docs'>/api/docs</a></p>")
