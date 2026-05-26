#!/usr/bin/env python3
import json, sys
from pathlib import Path
required = ["skill_id", "version", "stage", "type", "inputs", "outputs", "quality_gates", "workflow_interface", "owner"]
for arg in sys.argv[1:]:
    data = json.loads(Path(arg).read_text(encoding="utf-8"))
    missing = [key for key in required if key not in data]
    if missing:
        raise SystemExit(f"{arg}: 缺少字段 {missing}")
print("ok")
