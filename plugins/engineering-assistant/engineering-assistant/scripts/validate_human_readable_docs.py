#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    index_path = root / "docs/00-index/artifact-index.json"
    if not index_path.exists():
        raise SystemExit("missing docs/00-index/artifact-index.json")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    artifacts = index.get("artifacts", [])
    by_path = {item.get("path"): item for item in artifacts if isinstance(item, dict)}
    errors = []
    for item in artifacts:
        path = item.get("path", "")
        status = item.get("status")
        if not path.startswith("docs/") or not path.endswith(".md"):
            continue
        if status not in {"final", "approved"}:
            continue
        html_path = "docs/human-readable/" + Path(path).with_suffix(".html").name
        html_item = by_path.get(html_path)
        if not (root / html_path).exists():
            errors.append(f"missing human-readable html for {path}: {html_path}")
            continue
        if html_item and html_item.get("agent_source") is not False:
            errors.append(f"html artifact must be agent_source=false: {html_path}")
        text = (root / html_path).read_text(encoding="utf-8")
        if "Agent source of truth" not in text:
            errors.append(f"html artifact missing source-of-truth notice: {html_path}")
    if errors:
        raise SystemExit("\n".join(errors))
    print("ok")


if __name__ == "__main__":
    main()
