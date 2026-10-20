import os
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
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# ==========================================
# GAME10 - SINGLE FILE RAILWAY BACKEND
# ==========================================

app = FastAPI(title="Game10 Backend", version="2.8.2")

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

# GITHUB CONFIGURATION WITH TOKEN
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "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").strip()
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "").strip()
GITHUB_WORKFLOW = os.getenv("GITHUB_WORKFLOW", "build-apk.yml").strip()
GITHUB_REF = os.getenv("GITHUB_REF", "main").strip()

# ==========================================
# ALL AI API KEYS & CONFIGURATIONS
# ==========================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6L8w4DyW5YqFmXgRztfse2qGf1").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "gsk_mTazx3IPoh3WkzFMSDgbWGdyb3FYOLOg").strip()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "mstrl_Yl1YWz27Nbr59MSLGG6wbvZzHI6").strip()
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "xEpKAy9E56hlJwvQcadq7sIoykU8NobtJu").strip()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-4f6472053812dee9ff9f8b01f9d00").strip()
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "key_Cg7cXYgH4gjV5aaAQCG5t").strip()
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "r8_7E4ykYK8IrRPwJFGNMjWLi7Czs").strip()
SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY", "4a6f8dbe-40df-47c8-b10a-34c56b3").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "sk-or-v1-1981e6c4feb5da0cf1295").strip()


# ==========================================
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
        raise HTTPException(503, "GITHUB_TOKEN is not configured.")

    if not re.fullmatch(r"[^/\s]+/[^/\s]+", GITHUB_REPOSITORY):
        raise HTTPException(503, "Set GITHUB_REPOSITORY as owner/repository.")

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
            f"GitHub {action} failed (HTTP {response.status_code}). {detail[:300]}"
        )


def clean_html_output(text: str) -> str:
    return re.sub(r"^```(?:html)?\s*|\s*```$", "", text, flags=re.I).strip()


# ==========================================
# HOME AND HEALTH
# ==========================================

@app.get("/")
def home():
    return {
        "app": "Game10 Backend",
        "status": "running",
        "fallback_chain": ["gemini", "groq", "deepseek", "mistral", "openrouter", "together", "sambanova", "cohere", "replicate"],
        "active_ai_providers": {
            "gemini": bool(GEMINI_API_KEY),
            "groq": bool(GROQ_API_KEY),
            "deepseek": bool(DEEPSEEK_API_KEY),
            "mistral": bool(MISTRAL_API_KEY),
            "openrouter": bool(OPENROUTER_API_KEY),
            "together": bool(TOGETHER_API_KEY),
            "sambanova": bool(SAMBANOVA_API_KEY),
            "cohere": bool(COHERE_API_KEY),
            "replicate": bool(REPLICATE_API_TOKEN),
        }
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "github_build_configured": bool(GITHUB_TOKEN and GITHUB_REPOSITORY),
        "public_url_configured": bool(PUBLIC_BASE_URL),
    }


# ==========================================
# MULTI-AI FALLBACK GENERATION (9 PROVIDERS)
# ==========================================

@app.post("/api/generate")
def generate_game(body: GenerateInput):
    system_instruction = (
        "Create a complete playable HTML5 game as one self-contained HTML document. "
        "Include CSS and JavaScript in the same file. Return only raw HTML code, without markdown code fences."
    )
    user_prompt = f"Game title: {body.name}. User request: {body.prompt}"
    errors = []

    # 1. GEMINI
    if GEMINI_API_KEY:
        prompt = f"{system_instruction} {user_prompt}"
        models = list(dict.fromkeys([
            GEMINI_MODEL,
            "gemini-1.5-flash",
            "gemini-2.5-flash",
            "gemini-3.8-flash",
            "gemini-flash-latest"
        ]))
        for model in models:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                response = requests.post(
                    endpoint,
                    params={"key": GEMINI_API_KEY},
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=(10, 35),
                )
                data = response.json() if response.ok else {}
                if response.ok:
                    html = clean_html_output(data["candidates"][0]["content"]["parts"][0]["text"])
                    if "<html" in html.lower() or "<!doctype html" in html.lower():
                        return {"name": body.name, "html": html, "model": model, "provider": "gemini"}
            except Exception as exc:
                errors.append(f"Gemini ({model}): {str(exc)}")

    # 2. GROQ
    if GROQ_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_prompt}]
            }
            res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=40)
            if res.ok:
                html = clean_html_output(res.json()["choices"][0]["message"]["content"])
                if "<html" in html.lower() or "<!doctype html" in html.lower():
                    return {"name": body.name, "html": html, "model": "llama-3.3-70b-versatile", "provider": "groq"}
        except Exception as exc:
            errors.append(f"Groq: {str(exc)}")

    # 3. DEEPSEEK
    if DEEPSEEK_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_prompt}]
            }
            res = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=40)
            if res.ok:
                html = clean_html_output(res.json()["choices"][0]["message"]["content"])
                if "<html" in html.lower() or "<!doctype html" in html.lower():
                    return {"name": body.name, "html": html, "model": "deepseek-chat", "provider": "deepseek"}
        except Exception as exc:
            errors.append(f"DeepSeek: {str(exc)}")

    # 4. MISTRAL
    if MISTRAL_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "mistral-large-latest",
                "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_prompt}]
            }
            res = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload, timeout=40)
            if res.ok:
                html = clean_html_output(res.json()["choices"][0]["message"]["content"])
                if "<html" in html.lower() or "<!doctype html" in html.lower():
                    return {"name": body.name, "html": html, "model": "mistral-large-latest", "provider": "mistral"}
        except Exception as exc:
            errors.append(f"Mistral: {str(exc)}")

    # 5. OPENROUTER
    if OPENROUTER_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "anthropic/claude-3.5-sonnet",
                "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_prompt}]
            }
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=40)
            if res.ok:
                html = clean_html_output(res.json()["choices"][0]["message"]["content"])
                if "<html" in html.lower() or "<!doctype html" in html.lower():
                    return {"name": body.name, "html": html, "model": "anthropic/claude-3.5-sonnet", "provider": "openrouter"}
        except Exception as exc:
            errors.append(f"OpenRouter: {str(exc)}")

    # 6. TOGETHER AI
    if TOGETHER_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {TOGETHER_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_prompt}]
            }
            res = requests.post("https://api.together.xyz/v1/chat/completions", headers=headers, json=payload, timeout=40)
            if res.ok:
                html = clean_html_output(res.json()["choices"][0]["message"]["content"])
                if "<html" in html.lower() or "<!doctype html" in html.lower():
                    return {"name": body.name, "html": html, "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "provider": "together"}
        except Exception as exc:
            errors.append(f"Together: {str(exc)}")

    # 7. SAMBANOVA
    if SAMBANOVA_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {SAMBANOVA_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "Meta-Llama-3.3-70B-Instruct",
                "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_prompt}]
            }
            res = requests.post("https://api.sambanova.ai/v1/chat/completions", headers=headers, json=payload, timeout=40)
            if res.ok:
                html = clean_html_output(res.json()["choices"][0]["message"]["content"])
                if "<html" in html.lower() or "<!doctype html" in html.lower():
                    return {"name": body.name, "html": html, "model": "Meta-Llama-3.3-70B-Instruct", "provider": "sambanova"}
        except Exception as exc:
            errors.append(f"SambaNova: {str(exc)}")

    # 8. COHERE
    if COHERE_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {COHERE_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "command-r-plus",
                "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_prompt}]
            }
            res = requests.post("https://api.cohere.com/compatibility/v1/chat/completions", headers=headers, json=payload, timeout=40)
            if res.ok:
                html = clean_html_output(res.json()["choices"][0]["message"]["content"])
                if "<html" in html.lower() or "<!doctype html" in html.lower():
                    return {"name": body.name, "html": html, "model": "command-r-plus", "provider": "cohere"}
        except Exception as exc:
            errors.append(f"Cohere: {str(exc)}")

    # 9. REPLICATE
    if REPLICATE_API_TOKEN:
        try:
            headers = {"Authorization": f"Bearer {REPLICATE_API_TOKEN}", "Content-Type": "application/json", "Prefer": "wait"}
            payload = {
                "version": "meta/meta-llama-3-70b-instruct",
                "input": {"prompt": f"{system_instruction}\n\n{user_prompt}", "max_new_tokens": 4000}
            }
            res = requests.post("https://api.replicate.com/v1/predictions", headers=headers, json=payload, timeout=45)
            if res.ok:
                data = res.json()
                output = data.get("output", "")
                if isinstance(output, list):
                    output = "".join(output)
                html = clean_html_output(output)
                if "<html" in html.lower() or "<!doctype html" in html.lower():
                    return {"name": body.name, "html": html, "model": "meta-llama-3-70b-instruct", "provider": "replicate"}
        except Exception as exc:
            errors.append(f"Replicate: {str(exc)}")

    raise HTTPException(
        502,
        "All AI providers and fallback mechanisms failed sequentially. Details: " + "; ".join(errors)[:1000]
    )


# ==========================================
# SAVE & MANAGE GAMES (API ONLY)
# ==========================================

@app.post("/api/games")
def create_game(body: GameInput):
    if not body.html.strip():
        raise HTTPException(400, "Game HTML is empty.")

    game_id = uuid.uuid4().hex[:12]
    folder = GAMES / game_id
    folder.mkdir(parents=True, exist_ok=False)

    (folder / "index.html").write_text(body.html, encoding="utf-8")

    record = {
        "id": game_id,
        "name": body.name,
        "status": "saved",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    json_write(folder / "record.json", record)
    return record


@app.get("/api/games")
def list_games():
    items = []
    for folder in GAMES.iterdir():
        if folder.is_dir():
            record = json_read(folder / "record.json")
            if record:
                items.append(record)
    return sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)


@app.get("/api/games/{game_id}")
def game_record(game_id: str):
    if not valid_id(game_id):
        raise HTTPException(400, "Invalid game ID.")
    record = json_read(GAMES / game_id / "record.json")
    if not record:
        raise HTTPException(404, "Game not found.")
    return record


# नया राउट: GitHub Actions के लिए सीधे असली HTML फाइल सर्व करेगा
@app.get("/api/games/{game_id}/html")
def get_game_html(game_id: str):
    if not valid_id(game_id):
        raise HTTPException(400, "Invalid game ID.")
    game_file = GAMES / game_id / "index.html"
    if not game_file.is_file():
        raise HTTPException(404, "Game HTML not found.")
    return FileResponse(path=str(game_file), media_type="text/html")


# ==========================================
# APK BUILD THROUGH GITHUB ACTIONS
# ==========================================

@app.post("/api/builds")
def request_build(body: BuildInput):
    if not valid_id(body.game_id):
        raise HTTPException(400, "Invalid game_id.")

    game_file = GAMES / body.game_id / "index.html"
    if not game_file.is_file():
        raise HTTPException(404, "Save the game before requesting an APK build.")

    headers = github_headers()
    build_id = uuid.uuid4().hex[:12]
    dispatch_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/workflows/{GITHUB_WORKFLOW}/dispatches"

    payload = {
        "ref": GITHUB_REF,
        "inputs": {"build_id": build_id, "game_id": body.game_id, "backend_url": PUBLIC_BASE_URL},
    }

    try:
        response = requests.post(dispatch_url, headers=headers, json=payload, timeout=25)
    except requests.RequestException:
        raise HTTPException(502, "Could not connect to GitHub Actions.")

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


def find_run(build_id: str) -> Optional[dict]:
    headers = github_headers()
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/workflows/{GITHUB_WORKFLOW}/runs"
    try:
        response = requests.get(url, headers=headers, params={"per_page": 100}, timeout=25)
    except requests.RequestException:
        raise HTTPException(502, "Could not contact GitHub.")

    github_api_error(response, "workflow status lookup")
    for run in response.json().get("workflow_runs", []):
        title = str(run.get("display_title") or run.get("name") or "")
        if build_id in title:
            return run
    return None


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


@app.get("/api/builds/{build_id}/download")
def download_apk(build_id: str):
    if not valid_id(build_id):
        raise HTTPException(400, "Invalid build ID.")

    record = json_read(BUILDS / f"{build_id}.json")
    if not record:
        raise HTTPException(404, "Build not found.")

    run = find_run(build_id)
    if not run or run.get("status") != "completed" or run.get("conclusion") != "success":
        raise HTTPException(409, "APK is not ready yet.")

    headers = github_headers()
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/runs/{run['id']}/artifacts"

    try:
        response = requests.get(url, headers=headers, params={"per_page": 100}, timeout=25)
    except requests.RequestException:
        raise HTTPException(502, "Could not fetch GitHub artifacts.")

    github_api_error(response, "artifact lookup")
    expected = f"game10-apk-{build_id}"
    artifact = next((item for item in response.json().get("artifacts", []) if item.get("name") == expected and not item.get("expired")), None)

    if not artifact:
        raise HTTPException(404, f"Artifact {expected} not found.")

    try:
        archive_response = requests.get(artifact["archive_download_url"], headers=headers, timeout=90)
    except requests.RequestException:
        raise HTTPException(502, "Could not download artifact.")

    github_api_error(archive_response, "artifact download")

    temp_dir = Path(tempfile.mkdtemp(prefix="game10-"))
    archive_path = temp_dir / "artifact.zip"
    archive_path.write_bytes(archive_response.content)
    apk_path = temp_dir / f"Game10-{build_id}.apk"

    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".apk")]
            if not names:
                raise HTTPException(404, "No APK found in ZIP.")
            apk_path.write_bytes(archive.read(names[0]))
    except zipfile.BadZipFile:
        raise HTTPException(502, "Invalid ZIP file.")

    return FileResponse(path=str(apk_path), media_type="application/vnd.android.package-archive", filename=apk_path.name)
