from pathlib import Path
import json

ROOT = Path.home() / "game-builder"

PACKAGES = {
    "admob": "@capacitor-community/admob",
    "startio": "cordova-plugin-startapp-ads",
    "facebook": "cordova-facebook-audience-network",
    "unity": "cordova-plugin-unityads",
}

ROTATION = ["admob", "unity", "startio", "meta"]

def attach_to_project(project_dir):
    project = Path(project_dir)
    package_json = project / "package.json"

    if not package_json.exists():
        raise FileNotFoundError(f"package.json not found: {package_json}")

    data = json.loads(package_json.read_text(encoding="utf-8"))
    deps = data.setdefault("dependencies", {})

    for name, package in PACKAGES.items():
        deps.setdefault(package, "installed")

    config = {
        "rotation": ROTATION,
        "intervalSeconds": 14,
        "masterAndUserIds": True,
        "plugins": PACKAGES,
        "adminCreatorSkip": True,
    }

    out = project / "ad-config.json"
    out.write_text(json.dumps(config, indent=2), encoding="utf-8")
    package_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    print("ADS INJECTOR ATTACHED")
    print("AdMob + Start.io + Meta + Unity configuration attached")
    print("Master IDs + User IDs: supported")
    print("Rotation:", " -> ".join(ROTATION))
    print("Interval: 14 seconds")
    print("Admin/Creator skip: enabled")
    print("NOTE: Native SDK installation/sync is required during Android build.")

if __name__ == "__main__":
    print("Ready: call attach_to_project('/path/to/generated/project')")
