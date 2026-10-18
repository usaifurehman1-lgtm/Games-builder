import os
import re
import json
import uuid
import zipfile
import tempfile
import logging

from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

load_dotenv()

# ==========================================
# GAME10 - COMPLETE RAILWAY BACKEND
# ==========================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("game10")

app = FastAPI(
    title="Game10 Backend",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ==========================================
# STORAGE CONFIGURATION
# ==========================================

DATA = Path(os.getenv("DATA_DIR", "data"))
GAMES = DATA / "games"
BUILDS = DATA / "builds"

GAMES.mkdir(parents=True, exist_ok=True)
BUILDS.mkdir(parents=True, exist_ok=True)

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL", ""
).rstrip("/")

# ==========================================
# AI API KEYS
# ==========================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
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
SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "").strip()

# ==========================================
# GITHUB ACTIONS CONFIGURATION
# ==========================================

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()

GITHUB_REPOSITORY = os.getenv(
    "GITHUB_REPOSITORY", ""
).strip()

GITHUB_WORKFLOW = os.getenv(
    "GITHUB_WORKFLOW", "build-apk.yml"
).strip()

GITHUB_REF = os.getenv(
    "GITHUB_REF", "main"
).strip()

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

    path.write_text(
        json.dumps(value, indent=2),
        encoding="utf-8",
    )


def github_headers() -> dict:
    if not GITHUB_TOKEN:
        raise HTTPException(
            503,
            "GITHUB_TOKEN is not configured in Railway.",
        )

    if not re.fullmatch(
        r"[^/\s]+/[^/\s]+",
        GITHUB_REPOSITORY,
    ):
        raise HTTPException(
            503,
            "Set GITHUB_REPOSITORY as owner/repository.",
        )

    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_api_error(
    response: requests.Response,
    action: str,
):
    if not response.ok:
        detail = ""

        try:
            detail = response.json().get("message", "")
        except (ValueError, AttributeError):
            pass

        raise HTTPException(
            502,
            f"GitHub {action} failed "
            f"(HTTP {response.status_code}). "
            f"{detail[:300]}",
        )


# ==========================================
# AI PROVIDER CONFIGURATION
# ==========================================

AI_PROVIDERS = [
    {
        "name": "Gemini",
        "key": GEMINI_API_KEY,
        "url": (
            "https://generativelanguage.googleapis.com/"
            "v1beta/openai/chat/completions"
        ),
        "model": os.getenv(
            "GEMINI_MODEL", "gemini-2.5-flash"
        ),
        "style": "openai",
    },
    {
        "name": "Groq",
        "key": GROQ_API_KEY,
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": os.getenv(
            "GROQ_MODEL", "llama-3.3-70b-versatile"
        ),
        "style": "openai",
    },
    {
        "name": "Cerebras",
        "key": CEREBRAS_API_KEY,
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": os.getenv(
            "CEREBRAS_MODEL", "llama-3.3-70b"
        ),
        "style": "openai",
    },
    {
        "name": "Mistral",
        "key": MISTRAL_API_KEY,
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": os.getenv(
            "MISTRAL_MODEL", "mistral-small-latest"
        ),
        "style": "openai",
    },
    {
        "name": "Cohere",
        "key": COHERE_API_KEY,
        "url": (
            "https://api.cohere.com/compatibility/v1/"
            "chat/completions"
        ),
        "model": os.getenv(
            "COHERE_MODEL", "command-a-03-2025"
        ),
        "style": "openai",
    },
    {
        "name": "DeepSeek",
        "key": DEEPSEEK_API_KEY,
        "url": "https://api.deepseek.com/chat/completions",
        "model": os.getenv(
            "DEEPSEEK_MODEL", "deepseek-chat"
        ),
        "style": "openai",
    },
    {
        "name": "Together AI",
        "key": TOGETHER_API_KEY,
        "url": "https://api.together.xyz/v1/chat/completions",
        "model": os.getenv(
            "TOGETHER_MODEL",
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        ),
        "style": "openai",
    },
    {
        "name": "Fireworks AI",
        "key": FIREWORKS_API_KEY,
        "url": (
            "https://api.fireworks.ai/inference/v1/"
            "chat/completions"
        ),
        "model": os.getenv(
            "FIREWORKS_MODEL",
            "accounts/fireworks/models/"
            "llama-v3p3-70b-instruct",
        ),
        "style": "openai",
    },
    {
        "name": "Perplexity",
        "key": PERPLEXITY_API_KEY,
        "url": "https://api.perplexity.ai/chat/completions",
        "model": os.getenv(
            "PERPLEXITY_MODEL", "sonar"
        ),
        "style": "openai",
    },
    {
        "name": "AI21",
        "key": AI21_API_KEY,
        "url": "https://api.ai21.com/studio/v1/chat/completions",
        "model": os.getenv(
            "AI21_MODEL", "jamba-mini"
        ),
        "style": "openai",
    },
    {
        "name": "Replicate",
        "key": REPLICATE_API_TOKEN,
        "url": "https://api.replicate.com/v1/predictions",
        "model": os.getenv(
            "REPLICATE_MODEL_VERSION", ""
        ),
        "style": "replicate",
    },
    {
        "name": "SambaNova",
        "key": SAMBANOVA_API_KEY,
        "url": "https://api.sambanova.ai/v1/chat/completions",
        "model": os.getenv(
            "SAMBANOVA_MODEL",
            "Meta-Llama-3.3-70B-Instruct",
        ),
        "style": "openai",
    },
    {
        "name": "OpenRouter",
        "key": OPENROUTER_API_KEY,
        "url": (
            "https://openrouter.ai/api/v1/"
            "chat/completions"
        ),
        "model": os.getenv(
            "OPENROUTER_MODEL",
            "meta-llama/llama-3.3-70b-instruct",
        ),
        "style": "openai",
    },
    {
        "name": "Hugging Face",
        "key": HUGGINGFACE_API_KEY,
        "url": (
            "https://router.huggingface.co/v1/"
            "chat/completions"
        ),
        "model": os.getenv(
            "HUGGINGFACE_MODEL",
            "Qwen/Qwen2.5-72B-Instruct",
        ),
        "style": "openai",
    },
]


# ==========================================
# AI CALL - OPENAI-COMPATIBLE PROVIDERS
# ==========================================

def call_openai_compatible(
    provider: dict,
    prompt: str,
) -> str:

    headers = {
        "Authorization": f"Bearer {provider['key']}",
        "Content-Type": "application/json",
    }

    if provider["name"] == "Gemini":
        headers["Authorization"] = (
            f"Bearer {provider['key']}"
        )

    response = requests.post(
        provider["url"],
        headers=headers,
        json={
            "model": provider["model"],
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Create a complete playable HTML5 game. "
                        "Return a single full HTML document "
                        "with CSS and JavaScript included. "
                        "Do not return Markdown fences."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.7,
        },
        timeout=(10, 60),
    )

    response.raise_for_status()

    data = response.json()

    content = data["choices"][0]["message"]["content"]

    if isinstance(content, list):
        content = "".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict)
        )

    if not isinstance(content, str) or not content.strip():
        raise ValueError("Provider returned empty content.")

    return content.strip()


# ==========================================
# REPLICATE API
# ==========================================

def call_replicate(
    provider: dict,
    prompt: str,
) -> str:

    if not provider["model"]:
        raise ValueError(
            "Set REPLICATE_MODEL_VERSION to a supported "
            "Replicate model version."
        )

    headers = {
        "Authorization": (
            f"Bearer {provider['key']}"
        ),
        "Content-Type": "application/json",
        "Prefer": "wait=60",
    }

    response = requests.post(
        provider["url"],
        headers=headers,
        json={
            "version": provider["model"],
            "input": {
                "prompt": (
                    "Create a complete playable HTML5 game. "
                    "Return only HTML with inline CSS and "
                    "JavaScript. User request: "
                    + prompt
                ),
            },
        },
        timeout=(10, 70),
    )

    response.raise_for_status()
    data = response.json()

    if data.get("status") == "failed":
        raise ValueError(
            "Replicate prediction failed."
        )

    output = data.get("output", "")

    if isinstance(output, list):
        output = "".join(
            str(part) for part in output
        )

    if not isinstance(output, str) or not output.strip():
        raise ValueError(
            "Replicate returned no text. "
            "The model may require a different input format."
        )

    return output.strip()


# ==========================================
# CALL ONE AI PROVIDER
# ==========================================

def call_ai_provider(
    provider: dict,
    prompt: str,
) -> str:

    if provider["style"] == "replicate":
        return call_replicate(provider, prompt)

    return call_openai_compatible(provider, prompt)


# ==========================================
# CLEAN AND VALIDATE HTML
# ==========================================

def clean_game_html(html: str) -> str:

    html = re.sub(
        r"^\s*```(?:html)?\s*",
        "",
        html,
        flags=re.I,
    )

    html = re.sub(
        r"\s*```\s*$",
        "",
        html,
    )

    html = html.strip()

    if (
        "<html" not in html.lower()
        and "<!doctype html" not in html.lower()
    ):
        raise ValueError(
            "AI output is not a complete HTML document."
        )

    return html


# ==========================================
# HOME AND HEALTH
# ==========================================

@app.get("/")
def home():
    return {
        "app": "Game10 Backend",
        "status": "running",
        "version": "3.0.0",
        "features": [
            "game-save",
            "multi-provider-ai-fallback",
            "github-actions-apk-build",
            "apk-download",
        ],
        "ai_provider_count": len(AI_PROVIDERS),
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "ai_providers": {
            provider["name"]: bool(provider["key"])
            for provider in AI_PROVIDERS
        },
        "configured_ai_count": sum(
            bool(provider["key"])
            for provider in AI_PROVIDERS
        ),
        "github_build_configured": bool(
            GITHUB_TOKEN and GITHUB_REPOSITORY
        ),
        "public_url_configured": bool(
            PUBLIC_BASE_URL
        ),
    }


# ==========================================
# AI GAME GENERATION - FALLBACK WORKFLOW
# ==========================================

@app.post("/api/generate")
def generate_game(body: GenerateInput):

    prompt = (
        "Create a complete playable HTML5 game as one "
        "self-contained HTML document. Include CSS and "
        "JavaScript in the same file. Return only HTML, "
        "without Markdown fences.\n\n"
        f"Game title: {body.name}\n"
        f"User request: {body.prompt}"
    )

    errors = []

    for provider in AI_PROVIDERS:

        if not provider["key"]:
            logger.info(
                "Skipping %s: API key not configured.",
                provider["name"],
            )
            continue

        logger.info(
            "Trying AI provider: %s",
            provider["name"],
        )

        try:
            raw_html = call_ai_provider(
                provider,
                prompt,
            )

            html = clean_game_html(raw_html)

            logger.info(
                "AI generation succeeded: %s",
                provider["name"],
            )

            return {
                "name": body.name,
                "html": html,
                "provider": provider["name"],
                "model": provider["model"],
            }

        except requests.HTTPError as exc:

            status = (
                exc.response.status_code
                if exc.response is not None
                else 0
            )

            logger.warning(
                "%s failed with HTTP %s",
                provider["name"],
                status,
            )

            errors.append(
                f"{provider['name']}: HTTP {status}"
            )

            continue

        except requests.RequestException as exc:

            logger.warning(
                "%s network error: %s",
                provider["name"],
                type(exc).__name__,
            )

            errors.append(
                f"{provider['name']}: network error"
            )

            continue

        except (
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ) as exc:

            logger.warning(
                "%s returned invalid output: %s",
                provider["name"],
                type(exc).__name__,
            )

            errors.append(
                f"{provider['name']}: invalid response"
            )

            continue

    raise HTTPException(
        status_code=502,
        detail={
            "message": (
                "No configured AI provider generated "
                "a valid HTML game."
            ),
            "attempted_errors": errors,
            "configured_ai_count": sum(
                bool(provider["key"])
                for provider in AI_PROVIDERS
            ),
        },
    )


# ==========================================
# SAVE A GAME
# ==========================================

@app.post("/api/games")
def create_game(body: GameInput):

    if not body.html.strip():
        raise HTTPException(
            400,
            "Game HTML is empty.",
        )

    game_id = uuid.uuid4().hex[:12]

    folder = GAMES / game_id
    folder.mkdir(
        parents=True,
        exist_ok=False,
    )

    (folder / "index.html").write_text(
        body.html,
        encoding="utf-8",
    )

    record = {
        "id": game_id,
        "name": body.name,
        "status": "saved",
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    json_write(
        folder / "record.json",
        record,
    )

    game_url = (
        f"{PUBLIC_BASE_URL}/games/{game_id}"
        if PUBLIC_BASE_URL
        else f"/games/{game_id}"
    )

    return {
        **record,
        "game_url": game_url,
    }


# ==========================================
# OPEN SAVED GAME
# ==========================================

@app.get(
    "/games/{game_id}",
    response_class=HTMLResponse,
)
def get_game(game_id: str):

    if not valid_id(game_id):
        raise HTTPException(
            400,
            "Invalid game ID.",
        )

    file = GAMES / game_id / "index.html"

    if not file.is_file():
        raise HTTPException(
            404,
            "Game not found.",
        )

    return HTMLResponse(
        file.read_text(encoding="utf-8")
    )


# ==========================================
# LIST SAVED GAMES
# ==========================================

@app.get("/api/games")
def list_games():

    items = []

    for folder in GAMES.iterdir():

        if folder.is_dir():

            record = json_read(
                folder / "record.json"
            )

            if record:
                items.append(record)

    return sorted(
        items,
        key=lambda item: item.get(
            "created_at", ""
        ),
        reverse=True,
    )


# ==========================================
# GET GAME RECORD
# ==========================================

@app.get("/api/games/{game_id}")
def game_record(game_id: str):

    if not valid_id(game_id):
        raise HTTPException(
            400,
            "Invalid game ID.",
        )

    record = json_read(
        GAMES / game_id / "record.json"
    )

    if not record:
        raise HTTPException(
            404,
            "Game not found.",
        )

    return record


# ==========================================
# REQUEST REAL APK BUILD
# ==========================================

@app.post("/api/builds")
def request_build(body: BuildInput):

    if not valid_id(body.game_id):
        raise HTTPException(
            400,
            "Invalid game_id.",
        )

    game_file = (
        GAMES / body.game_id / "index.html"
    )

    if not game_file.is_file():
        raise HTTPException(
            404,
            "Save the game before requesting an APK build.",
        )

    headers = github_headers()

    build_id = uuid.uuid4().hex[:12]

    dispatch_url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_REPOSITORY}/actions/workflows/"
        f"{GITHUB_WORKFLOW}/dispatches"
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
            502,
            "Could not connect to GitHub Actions.",
        )

    if response.status_code != 204:
        github_api_error(
            response,
            "workflow dispatch",
        )

    record = {
        "id": build_id,
        "game_id": body.game_id,
        "status": "queued",
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "github_run_url": None,
    }

    json_write(
        BUILDS / f"{build_id}.json",
        record,
    )

    return record


# ==========================================
# FIND GITHUB ACTIONS RUN
# ==========================================

def find_run(build_id: str) -> Optional[dict]:

    headers = github_headers()

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_REPOSITORY}/actions/workflows/"
        f"{GITHUB_WORKFLOW}/runs"
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
            502,
            "Could not contact GitHub to check build status.",
        )

    github_api_error(
        response,
        "workflow status lookup",
    )

    for run in response.json().get(
        "workflow_runs", []
    ):

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
        raise HTTPException(
            400,
            "Invalid build ID.",
        )

    path = BUILDS / f"{build_id}.json"

    record = json_read(path)

    if not record:
        raise HTTPException(
            404,
            "Build not found.",
        )

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
# DOWNLOAD BUILT APK
# ==========================================

@app.get("/api/builds/{build_id}/download")
def download_apk(build_id: str):

    if not valid_id(build_id):
        raise HTTPException(
            400,
            "Invalid build ID.",
        )

    record = json_read(
        BUILDS / f"{build_id}.json"
    )

    if not record:
        raise HTTPException(
            404,
            "Build not found.",
        )

    run = find_run(build_id)

    if (
        not run
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
    ):
        raise HTTPException(
            409,
            "APK is not ready. Check build status "
            "and GitHub Actions logs.",
        )

    headers = github_headers()

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_REPOSITORY}/actions/runs/"
        f"{run['id']}/artifacts"
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
            502,
            "Could not fetch GitHub artifacts.",
        )

    github_api_error(
        response,
        "artifact lookup",
    )

    expected = f"game10-apk-{build_id}"

    artifact = next(
        (
            item
            for item in response.json().get(
                "artifacts", []
            )
            if item.get("name") == expected
            and not item.get("expired")
        ),
        None,
    )

    if not artifact:
        raise HTTPException(
            404,
            f"Artifact {expected} not found. "
            "Check workflow output.",
        )

    try:
        archive_response = requests.get(
            artifact["archive_download_url"],
            headers=headers,
            timeout=90,
        )

    except requests.RequestException:
        raise HTTPException(
            502,
            "Could not download the GitHub artifact.",
        )

    github_api_error(
        archive_response,
        "artifact download",
    )

    temp_dir = Path(
        tempfile.mkdtemp(prefix="game10-")
    )

    archive_path = temp_dir / "artifact.zip"

    archive_path.write_bytes(
        archive_response.content
    )

    apk_path = (
        temp_dir / f"Game10-{build_id}.apk"
    )

    try:
        with zipfile.ZipFile(
            archive_path
        ) as archive:

            names = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".apk")
            ]

            if not names:
                raise HTTPException(
                    404,
                    "Artifact ZIP contains no APK file.",
                )

            apk_path.write_bytes(
                archive.read(names[0])
            )

    except zipfile.BadZipFile:
        raise HTTPException(
            502,
            "GitHub returned an invalid artifact ZIP.",
        )

    return FileResponse(
        path=str(apk_path),
        media_type=(
            "application/vnd.android.package-archive"
        ),
        filename=apk_path.name,
    )
