#!/usr/bin/env python3
import json, sys
from pathlib import Path
for arg in sys.argv[1:]:
    data = json.loads(Path(arg).read_text(encoding="utf-8"))
    for rule in data.get("rules", []):
        if rule.get("status") == "approved" and rule.get("review_required", True):
            raise SystemExit(f"{arg}: approved 规则仍处于需评审状态")
print("ok")
