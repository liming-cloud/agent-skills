#!/usr/bin/env python3
import json, re, sys
from pathlib import Path

DOC_NUMBER = re.compile(r"^(REQ|CTX|HLD|DDD|DBD|RDS|MQD|DRR|CQR|CRR|RLP|RVF|RTR|KNO|RPT)-[A-Z0-9][A-Z0-9-]{1,40}-[0-9]{8}-[0-9]{3}$")
REQUIRED = ["document_number", "document_status", "retention_policy", "title", "owner", "source_artifacts"]
FORMAL_STATUSES = {"approved", "final"}
INTERMEDIATE_STATUSES = {"draft", "reviewing", "blocked", "waiting_for_input"}

errors = []
for arg in sys.argv[1:]:
    path = Path(arg)
    data = json.loads(path.read_text(encoding="utf-8"))
    for field in REQUIRED:
        if field not in data:
            errors.append(f"{path}: 缺少字段 {field}")
    if errors:
        continue
    if not DOC_NUMBER.match(str(data["document_number"])):
        errors.append(f"{path}: document_number 不符合编号规范")
    if data["document_status"] in INTERMEDIATE_STATUSES and data["retention_policy"] == "persist":
        errors.append(f"{path}: 中间过程文档不得 persist")
    if data["retention_policy"] == "persist" and data["document_status"] not in FORMAL_STATUSES:
        errors.append(f"{path}: 只有 approved/final 文档可以 persist")
if errors:
    raise SystemExit("\n".join(errors))
print("ok")
