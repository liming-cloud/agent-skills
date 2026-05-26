#!/usr/bin/env python3
import hashlib
import html.parser
import json
import re
from datetime import datetime, timezone
from pathlib import Path

CONTROL_DIR = Path("artifacts/_control")

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def ensure_control_dir(root: Path) -> Path:
    path = root / CONTROL_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path

def validate_target_project_root(root: Path) -> Path:
    root = root.resolve()
    plugin_markers = [
        root / ".codex-plugin" / "plugin.json",
        root / "engineering-assistant" / "scripts" / "control_runtime.py",
        root / "scripts" / "control_runtime.py",
    ]
    if any(marker.exists() for marker in plugin_markers):
        raise SystemExit("--root must be the target project root, not the Codex plugin directory")
    return root

def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

class _HTMLTextExtractor(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

def read_text_artifact(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".html", ".htm"}:
        parser = _HTMLTextExtractor()
        parser.feed(raw)
        return "\n".join(parser.parts)
    return raw

def compact_lines(text: str, limit: int = 24):
    lines = []
    metadata_prefixes = ("document_number:", "document_status:", "retention_policy:", "owner:", "approval_status:", "language:", "source_artifacts:")
    source_path_prefixes = ("artifacts/", "docs/", "engineering-assistant/")
    for raw in text.splitlines():
        item = re.sub(r"\s+", " ", raw.strip(" -*\t"))
        lowered = item.lower()
        if not item or item.startswith("|") or lowered.startswith(metadata_prefixes):
            continue
        if item.startswith("#") or item.startswith(source_path_prefixes):
            continue
        if len(item) >= 8 and item not in lines:
            lines.append(item[:240])
        if len(lines) >= limit:
            break
    return lines

def _append_unique(result, item: str):
    if item and item not in result:
        result.append(item)

def _append_path_pattern(result, item: str):
    normalized = item.strip().strip("`'\"，,.;；:()[]{}").strip("./")
    if not normalized or any(part in normalized for part in ["..", "://", "\\"]) or " " in normalized:
        return
    path_roots = ("backend/", "frontend/", "deploy/", "docs/", "artifacts/", "engineering-assistant/", "scripts/", "src/", "test/", "tests/")
    file_like = re.search(r"\.(?:java|kt|go|py|ts|tsx|js|jsx|vue|sql|xml|yaml|yml|json|md)$", normalized)
    if not file_like and not normalized.startswith(path_roots):
        return
    if normalized not in {"package.json", "tsconfig.json"}:
        _append_unique(result, normalized)

def _append_project_module_pattern(result, token: str):
    normalized = token.strip().strip("`'\"，,.;；:()[]{}").strip("./")
    if not normalized or " " in normalized:
        return
    if normalized == "contexts/*":
        _append_unique(result, "backend/contexts/*")
    elif normalized.startswith("platform-"):
        _append_unique(result, f"backend/platform-boot/{normalized}")
    elif normalized.startswith("shared-"):
        _append_unique(result, f"backend/platform-shared/{normalized}")
    elif normalized.startswith("infra-"):
        _append_unique(result, f"backend/platform-infrastructure/{normalized}")

def find_file_patterns(text: str):
    result = []
    for item in re.findall(r"[\w./*-]+\.(?:java|kt|go|py|tsx|ts|jsx|json|js|vue|sql|xml|yaml|yml|md)(?=$|[\s`'\"<>),，。;；])", text):
        _append_path_pattern(result, item)
    for item in re.findall(r"`([^`\n]+)`", text):
        for part in re.split(r"[,，;；\s]+", item):
            _append_path_pattern(result, part)
            _append_project_module_pattern(result, part)
    for item in re.findall(r"\b(?:backend|frontend|deploy|docs|artifacts|engineering-assistant|scripts|src|test|tests)(?:/[A-Za-z0-9._*{}-]+)+/?", text):
        _append_path_pattern(result, item)
    if re.search(r"\bbackend\b|后端|Maven|Spring Boot", text, re.IGNORECASE):
        for item in ["pom.xml", "backend/pom.xml", "backend/platform-boot/*", "backend/platform-shared/*", "backend/platform-infrastructure/*", "backend/contexts/*"]:
            _append_unique(result, item)
    if re.search(r"\bfrontend\b|前端|React|Vite", text, re.IGNORECASE):
        for item in ["frontend/console-web", "frontend/console-web/src", "frontend/console-web/package.json"]:
            _append_unique(result, item)
    if re.search(r"\bdeploy\b|部署|Docker|真实环境", text, re.IGNORECASE):
        _append_unique(result, "deploy/")
    return result[:120]

def update_artifact_index(root: Path, name: str, path: Path, artifact_type: str, producer: str):
    control = ensure_control_dir(root)
    index_path = control / "artifact-index.json"
    data = read_json(index_path, {"artifacts": {}})
    rel = str(path.relative_to(root)) if path.is_absolute() else str(path)
    data["artifacts"][name] = {"name": name, "path": rel, "artifact_type": artifact_type, "producer": producer, "updated_at": now_iso()}
    data["updated_at"] = now_iso()
    write_json(index_path, data)
