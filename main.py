

from dotenv import load_dotenv
load_dotenv()

import os
from dotenv import load_dotenv
load_dotenv()
import re
import json
import uuid
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

# ==========================================
# GAME10 - SINGLE FILE RAILWAY BACKEND
# ==========================================

app = FastAPI(title="Game10 Backend", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

DATA = Path(os.getenv("DATA_DIR", "data"))
GAMES = DATA / "games"
BUILDS = DATA / "builds"

GAMES.mkdir(parents=True, exist_ok=True)
BUILDS.mkdir(parents=True, exist_ok=True)

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "").strip()
GITHUB_WORKFLOW = os.getenv("GITHUB_WORKFLOW", "build-apk.yml").strip()
GITHUB_REF = os.getenv("GITHUB_REF", "main").strip()


# PYTHON AI API KEYS
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "").strip()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "").strip()
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "").strip()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "").strip()
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY", "").strip()
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "").strip()
AI21_API_KEY = os.getenv("AI21_API_KEY", "").strip()
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "").strip()

# ==========================================
SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "").strip()

# REQUEST MODELS
# ==========================================

class GameInput(BaseModel):
    name: str = Field(default="My Game", max_length=100)
    html: str = Field(min_length=1, max_length=2_000_000)


class GenerateInput(BaseModel):
    prompt: str = Field(min_length=3, max_length=12000)
    name: str = Field(default="My Game", max_length=100)


class BuildInput(BaseModel):
    game_id: str = Field(min_length=12, max_length=12)


# ==========================================
# HELPERS
# ==========================================

def valid_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-f0-9]{12}", value or ""))


def json_read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def json_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def github_headers() -> dict:
    if not GITHUB_TOKEN:
        raise HTTPException(
            503, "GITHUB_TOKEN is not configured in Railway."
        )

    if not re.fullmatch(r"[^/\s]+/[^/\s]+", GITHUB_REPOSITORY):
        raise HTTPException(
            503, "Set GITHUB_REPOSITORY as owner/repository."
        )

    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_api_error(response: requests.Response, action: str):
    if not response.ok:
        detail = ""
        try:
            detail = response.json().get("message", "")
        except (ValueError, AttributeError):
            pass

        raise HTTPException(
            502,
            f"GitHub {action} failed (HTTP {response.status_code}). "
            f"{detail[:300]}"
        )


# ==========================================
# HOME AND HEALTH
# ==========================================

@app.get("/")
def home():
    return {
        "app": "Game10 Backend",
        "status": "running",
        "features": [
            "game-save",
            "Gemini-generation",
            "GitHub-Actions-APK-build"
        ]
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "gemini_configured": bool(GEMINI_API_KEY),
        "github_build_configured": bool(
            GITHUB_TOKEN and GITHUB_REPOSITORY
        ),
        "public_url_configured": bool(PUBLIC_BASE_URL),
    }


# ==========================================
# GEMINI AI GAME GENERATION
# ==========================================

@app.post("/api/generate")
def generate_game(body: GenerateInput):
    if not GEMINI_API_KEY:
        raise HTTPException(503, "Set GEMINI_API_KEY in Railway Variables.")

    prompt = (
        "Create a complete playable HTML5 game as one "
        "self-contained HTML document. Include CSS and JavaScript "
        "in the same file. Return only HTML, without Markdown fences. "
        "Game title: " + body.name +
        ". User request: " + body.prompt
    )

    models = list(dict.fromkeys([
        GEMINI_MODEL,
        "gemini-1.5-flash",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.5-flash-preview-tts",
        "gemini-2.5-pro-preview-tts",
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
        "gemini-pro-latest",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash-image",
        "gemini-3-flash-preview",
        "gemini-3.1-pro-preview",
        "gemini-3.1-pro-preview-customtools",
        "gemini-3.1-flash-lite-preview",
        "gemini-3.1-flash-lite",
        "gemini-3-pro-image-preview",
        "gemini-3-pro-image",
        "nano-banana-pro-preview",
        "gemini-3.1-flash-image-preview",
        "gemini-3.1-flash-image",
        "gemini-3.1-flash-lite-image",
        "gemini-nano-banana-2.1",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-omni-flash-preview",
        "gemini-omni-1.1-flash",
        "gemini-3.5-transcribe",
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.8-flash",
        "gemini-4-argon",
        "lyria-3-clip-preview",
        "lyria-3-pro-preview",
        "lyria-3.5",
        "gemini-3.1-flash-tts-preview",
        "gemini-3.8-flash-tts",
        "gemini-3.8-flash-lite-tts",
        "gemini-robotics-er-2-preview",
        "gemini-2.5-computer-use-preview-10-2025",
        "antigravity-preview-05-2026",
        "antigravity-preview-09-2026",
        "antigravity-preview-latest",
        "deep-research-max-preview-04-2026",
        "deep-research-preview-04-2026",
        "deep-research-pro-preview-12-2025",
    ]))
    errors = []

    for model in models:
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        try:
            response = requests.post(
                endpoint,
                params={"key": GEMINI_API_KEY},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=(10, 35),
            )
            try:
                data = response.json()
            except ValueError:
                data = {}
        except requests.RequestException as exc:
            errors.append(f"{model}: {type(exc).__name__}")
            continue

        if not response.ok:
            message = data.get("error", {}).get("message", "Request failed")
            if response.status_code in (400, 404, 429, 500, 502, 503, 504):
                errors.append(f"{model}: HTTP {response.status_code}")
                continue
            raise HTTPException(502, message[:500])

        try:
            html = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError):
            errors.append(f"{model}: no generated text")
            continue

        html = re.sub(
            r"^```(?:html)?\s*|\s*```$",
            "",
            html,
            flags=re.I,
        ).strip()

        if "<html" not in html.lower() and "<!doctype html" not in html.lower():
            errors.append(f"{model}: output is not a full HTML document")
            continue

        return {"name": body.name, "html": html, "model": model}

    raise HTTPException(
        502,
        "All attempted Gemini models failed. Check model IDs and Railway "
        "GEMINI_API_KEY. Details: " + "; ".join(errors)[:800],
    )


# SAVE A GAME
# ==========================================

@app.post("/api/games")
def create_game(body: GameInput):
    if not body.html.strip():
        raise HTTPException(400, "Game HTML is empty.")

    game_id = uuid.uuid4().hex[:12]
    folder = GAMES / game_id
    folder.mkdir(parents=True, exist_ok=False)

    (folder / "index.html").write_text(
        body.html, encoding="utf-8"
    )

    record = {
        "id": game_id,
        "name": body.name,
        "status": "saved",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    json_write(folder / "record.json", record)

    game_url = (
        f"{PUBLIC_BASE_URL}/games/{game_id}"
        if PUBLIC_BASE_URL
        else f"/games/{game_id}"
    )

    return {**record, "game_url": game_url}


@app.get("/games/{game_id}", response_class=HTMLResponse)
def get_game(game_id: str):
    if not valid_id(game_id):
        raise HTTPException(400, "Invalid game ID.")

    file = GAMES / game_id / "index.html"

    if not file.is_file():
        raise HTTPException(404, "Game not found.")

    return HTMLResponse(
        file.read_text(encoding="utf-8")
    )


@app.get("/api/games")
def list_games():
    items = []

    for folder in GAMES.iterdir():
        if folder.is_dir():
            record = json_read(folder / "record.json")
            if record:
                items.append(record)

    return sorted(
        items,
        key=lambda item: item.get("created_at", ""),
        reverse=True
    )


@app.get("/api/games/{game_id}")
def game_record(game_id: str):
    if not valid_id(game_id):
        raise HTTPException(400, "Invalid game ID.")

    record = json_read(
        GAMES / game_id / "record.json"
    )

    if not record:
        raise HTTPException(404, "Game not found.")

    return record


# ==========================================
# START REAL APK BUILD THROUGH GITHUB ACTIONS
# ==========================================

@app.post("/api/builds")
def request_build(body: BuildInput):
    if not valid_id(body.game_id):
        raise HTTPException(400, "Invalid game_id.")

    game_file = GAMES / body.game_id / "index.html"

    if not game_file.is_file():
        raise HTTPException(
            404, "Save the game before requesting an APK build."
        )

    headers = github_headers()
    build_id = uuid.uuid4().hex[:12]

    dispatch_url = (
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}"
        f"/actions/workflows/{GITHUB_WORKFLOW}/dispatches"
    )

    payload = {
        "ref": GITHUB_REF,
        "inputs": {
            "build_id": build_id,
            "game_id": body.game_id,
            "backend_url": PUBLIC_BASE_URL,
        },
    }

    try:
        response = requests.post(
            dispatch_url,
            headers=headers,
            json=payload,
            timeout=25,
        )
    except requests.RequestException:
        raise HTTPException(
            502, "Could not connect to GitHub Actions."
        )

    if response.status_code != 204:
        github_api_error(response, "workflow dispatch")

    record = {
        "id": build_id,
        "game_id": body.game_id,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "github_run_url": None,
    }

    json_write(BUILDS / f"{build_id}.json", record)

    return record


# ==========================================
# FIND THE GITHUB BUILD RUN
# ==========================================

def find_run(build_id: str) -> Optional[dict]:
    headers = github_headers()

    url = (
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}"
        f"/actions/workflows/{GITHUB_WORKFLOW}/runs"
    )

    try:
        response = requests.get(
            url,
            headers=headers,
            params={"per_page": 100},
            timeout=25,
        )
    except requests.RequestException:
        raise HTTPException(
            502, "Could not contact GitHub to check build status."
        )

    github_api_error(response, "workflow status lookup")

    for run in response.json().get("workflow_runs", []):
        title = str(
            run.get("display_title")
            or run.get("name")
            or ""
        )

        if build_id in title:
            return run

    return None


# ==========================================
# CHECK BUILD STATUS
# ==========================================

@app.get("/api/builds/{build_id}")
def build_status(build_id: str):
    if not valid_id(build_id):
        raise HTTPException(400, "Invalid build ID.")

    path = BUILDS / f"{build_id}.json"
    record = json_read(path)

    if not record:
        raise HTTPException(404, "Build not found.")

    run = find_run(build_id)

    if run:
        if run.get("status") != "completed":
            state = "running"
        elif run.get("conclusion") == "success":
            state = "success"
        else:
            state = "failed"

        record.update({
            "status": state,
            "github_run_url": run.get("html_url"),
            "run_id": run.get("id"),
            "conclusion": run.get("conclusion"),
        })

        json_write(path, record)

    return record


# ==========================================
# DOWNLOAD THE BUILT APK
# ==========================================

@app.get("/api/builds/{build_id}/download")
def download_apk(build_id: str):
    if not valid_id(build_id):
        raise HTTPException(400, "Invalid build ID.")

    record = json_read(
        BUILDS / f"{build_id}.json"
    )

    if not record:
        raise HTTPException(404, "Build not found.")

    run = find_run(build_id)

    if (
        not run
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
    ):
        raise HTTPException(
            409,
            "APK is not ready. Check build status and GitHub Actions logs."
        )

    headers = github_headers()

    url = (
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}"
        f"/actions/runs/{run['id']}/artifacts"
    )

    try:
        response = requests.get(
            url,
            headers=headers,
            params={"per_page": 100},
            timeout=25,
        )
    except requests.RequestException:
        raise HTTPException(
            502, "Could not fetch GitHub artifacts."
        )

    github_api_error(response, "artifact lookup")

    expected = f"game10-apk-{build_id}"

    artifact = next(
        (
            item
            for item in response.json().get("artifacts", [])
            if item.get("name") == expected
            and not item.get("expired")
        ),
        None,
    )

    if not artifact:
        raise HTTPException(
            404,
            f"Artifact {expected} not found. Check workflow output."
        )

    try:
        archive_response = requests.get(
            artifact["archive_download_url"],
            headers=headers,
            timeout=90,
        )
    except requests.RequestException:
        raise HTTPException(
            502, "Could not download the GitHub artifact."
        )

    github_api_error(archive_response, "artifact download")

    temp_dir = Path(
        tempfile.mkdtemp(prefix="game10-")
    )

    archive_path = temp_dir / "artifact.zip"
    archive_path.write_bytes(archive_response.content)

    apk_path = temp_dir / f"Game10-{build_id}.apk"

    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = [
                name for name in archive.namelist()
                if name.lower().endswith(".apk")
            ]

            if not names:
                raise HTTPException(
                    404, "Artifact ZIP contains no APK file."
                )

            apk_path.write_bytes(
                archive.read(names[0])
            )

    except zipfile.BadZipFile:
        raise HTTPException(
            502, "GitHub returned an invalid artifact ZIP."
        )

    return FileResponse(
        path=str(apk_path),
        media_type="application/vnd.android.package-archive",
        filename=apk_path.name,
    )
