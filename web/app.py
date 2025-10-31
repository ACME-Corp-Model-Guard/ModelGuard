import os

import requests
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from mangum import Mangum

API_BASE = os.environ.get(
    "API_BASE", "https://<api-id>.execute-api.us-east-1.amazonaws.com/prod"
)

app = FastAPI(title="ModelGuard Web UI")
templates = Jinja2Templates(directory="web/templates")

app.mount("/static", StaticFiles(directory="web/static"), name="static")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Show model list fetched from existing enumerate endpoint."""
    try:
        resp = requests.get(f"{API_BASE}/get_search_by_name")
        models = resp.json().get("models", [])
    except Exception:
        models = []
    return templates.TemplateResponse(
        "index.html", {"request": request, "models": models}
    )


@app.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request) -> HTMLResponse:
    """Show the upload page."""
    return templates.TemplateResponse("upload.html", {"request": request})


@app.post("/upload", response_class=RedirectResponse)
def upload_model(file_url: str = Form(...)) -> RedirectResponse:
    """Proxy model upload to existing Lambda endpoint."""
    requests.post(f"{API_BASE}/post_artifact_upload", json={"file": file_url})
    return RedirectResponse("/", status_code=303)


handler = Mangum(app)  # Lambda Entry Point
