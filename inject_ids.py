import json
from pathlib import Path

CONFIG = Path("backend/config/ad-master-ids.json")
OUTPUT = Path("www/generated-ad-config.js")

data = json.loads(CONFIG.read_text())

# Build-time configuration.
# Do not put secret API keys/tokens here.
payload = json.dumps(data, separators=(",", ":"))

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    "window.__AD_CONFIG__ = " + payload + ";\n",
    encoding="utf-8"
)

print("SECURE BUILD CONFIG INJECTED")
print("Output:", OUTPUT)
print("Networks:", ", ".join(data.keys()))

# --- Ad backend integration ---
try:
    from backend.ad_backend_bridge import prepare_ad_backend
except ImportError:
    from ad_backend_bridge import prepare_ad_backend

def attach_ad_backend(master_ids=None, user_ids=None):
    prepare_ad_backend(
        master_ids=master_ids or {},
        user_ids=user_ids or {}
    )
    print("Ad backend attached to ID injection pipeline.")


# --- Ad backend integration ---
try:
    from backend.ad_backend_bridge import prepare_ad_backend
except ImportError:
    from ad_backend_bridge import prepare_ad_backend

def attach_ad_backend(master_ids=None, user_ids=None):
    prepare_ad_backend(
        master_ids=master_ids or {},
        user_ids=user_ids or {}
    )
    print("Ad backend attached to ID injection pipeline.")

