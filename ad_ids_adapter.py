from pathlib import Path
import json
from ad_backend_bridge import prepare_ad_backend

CONFIG = Path(__file__).resolve().parent / "ad_ids.json"

def load_ids():
    if not CONFIG.exists():
        return {}, {}

    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    return data.get("master", {}), data.get("user", {})

def attach_ids():
    master_ids, user_ids = load_ids()

    prepare_ad_backend(
        master_ids=master_ids,
        user_ids=user_ids
    )

    print("AD ID ADAPTER ATTACHED")
    print("Master IDs + User IDs -> backend")
    print("AdMob -> Unity -> Start.io -> Meta")
    print("14-second rotation configured")

if __name__ == "__main__":
    attach_ids()
