import json
import base64
from pathlib import Path

src = Path("backend/config/ad-master-ids.json")
out = Path("backend/config/ad-master-ids.obf")

data = json.loads(src.read_text(encoding="utf-8"))
raw = json.dumps(data, separators=(",", ":")).encode()

encoded = base64.b64encode(raw).decode()

out.write_text(encoded, encoding="utf-8")

print("ID PROTECTION FILE CREATED")
print("File:", out)
print("Length:", len(encoded))
