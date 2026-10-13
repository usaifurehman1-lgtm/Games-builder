import json
from pathlib import Path

def build_ad_config(master_ids, user_ids):
    return {
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
        "rotation": ["admob", "unity", "startio", "meta"],
        "interval_seconds": 14
    }

def inject_ad_config(target_file, master_ids, user_ids):
    target = Path(target_file)
    config = build_ad_config(master_ids, user_ids)

    target.write_text(
        json.dumps(config, indent=2),
        encoding="utf-8"
    )

    print("AD CONFIG INJECTED")
    print("Master IDs: AdMob + Unity + Start.io + Meta")
    print("User IDs:   AdMob + Unity + Start.io + Meta")
    print("Rotation:   AdMob -> Unity -> Start.io -> Meta")
    print("Interval:   14 seconds")

if __name__ == "__main__":
    print("Injector ready.")
