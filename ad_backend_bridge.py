from pathlib import Path
import json

BASE = Path(__file__).resolve().parent.parent

def prepare_ad_backend(user_ids=None, master_ids=None):
    user_ids = user_ids or {}
    master_ids = master_ids or {}

    config = {
        "master": {
            "admob": master_ids.get("admob"),
            "unity": master_ids.get("unity"),
            "startio": master_ids.get("startio"),
            "meta": master_ids.get("meta"),
        },
        "user": {
            "admob": user_ids.get("admob"),
            "unity": user_ids.get("unity"),
            "startio": user_ids.get("startio"),
            "meta": user_ids.get("meta"),
        },
        "plugins": {
            "admob": "@capacitor-community/admob",
            "startio": "cordova-plugin-startapp-ads",
            "unity": "cordova-plugin-unityads",
            "meta": "cordova-facebook-audience-network",
        },
        "rotation": ["admob", "unity", "startio", "meta"],
        "intervalSeconds": 14,
        "adminCreatorSkip": True,
    }

    output = BASE / "backend" / "ad_backend_config.json"
    output.write_text(
        json.dumps(config, indent=2),
        encoding="utf-8"
    )

    print("BACKEND AD CONFIG READY")
    print("Master + User IDs: attached")
    print("Plugins: AdMob + Unity + Start.io + Meta")
    print("Rotation: AdMob -> Unity -> Start.io -> Meta")
    print("Interval: 14 seconds")
    print("Admin/Creator skip: enabled")
    print(f"Config: {output}")

if __name__ == "__main__":
    prepare_ad_backend()
