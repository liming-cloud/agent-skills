#!/usr/bin/env python3
import json, sys
from pathlib import Path
valid = {"pass", "warn", "block", "require_human_review"}
for arg in sys.argv[1:]:
    data = json.loads(Path(arg).read_text(encoding="utf-8"))
    if data.get("gate_decision") not in valid:
        raise SystemExit(f"{arg}: gate_decision 不合法")
print("ok")
