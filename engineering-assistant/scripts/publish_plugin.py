#!/usr/bin/env python3
import argparse
import json
import shutil
from pathlib import Path

DEFAULT_CONFIG = Path(".agent/plugins/publish-config.json")


def load_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"missing publish config: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def expand(path_value: str) -> Path:
    return Path(path_value).expanduser().resolve()


def ensure_not_repo_path(repo_root: Path, path: Path) -> None:
    try:
        path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return
    raise SystemExit(f"refuse to publish into repository workspace: {path}")


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        raise SystemExit(f"missing source tree: {source}")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def marketplace_payload(config: dict) -> dict:
    plugin_name = config.get("plugin_name", "engineering-assistant")
    return {
        "name": config.get("name", "local-engineering"),
        "interface": config.get("interface", {"displayName": "Local Engineering Plugins"}),
        "plugins": [
            {
                "name": plugin_name,
                "source": {
                    "source": "local",
                    "path": "./" + config.get("plugin_relative_path", f"plugins/{plugin_name}").strip("/"),
                },
                "policy": config.get("policy", {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}),
                "category": config.get("category", "Productivity"),
            }
        ],
    }


def publish(repo_root: Path, config: dict, publish_root=None, marketplace_path=None) -> dict:
    plugin_name = config.get("plugin_name", "engineering-assistant")
    publish_root = publish_root or expand(config["publish_root"])
    marketplace_path = marketplace_path or expand(config.get("marketplace_path", str(publish_root / "marketplace.json")))
    plugin_relative = Path(config.get("plugin_relative_path", f"plugins/{plugin_name}"))
    plugin_root = publish_root / plugin_relative
    ensure_not_repo_path(repo_root, publish_root)
    ensure_not_repo_path(repo_root, marketplace_path)

    manifest = repo_root / "engineering-assistant" / "plugin" / "plugin.json"
    skills = repo_root / "skills"
    runtime = repo_root / "engineering-assistant"
    if not manifest.exists():
        raise SystemExit(f"missing plugin manifest source: {manifest}")

    plugin_root.parent.mkdir(parents=True, exist_ok=True)
    if plugin_root.exists():
        shutil.rmtree(plugin_root)
    (plugin_root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest, plugin_root / ".codex-plugin" / "plugin.json")
    copy_tree(skills, plugin_root / "skills")
    copy_tree(runtime, plugin_root / "engineering-assistant")

    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text(json.dumps(marketplace_payload(config), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "published",
        "plugin_root": str(plugin_root),
        "marketplace_path": str(marketplace_path),
        "plugin_manifest": str(plugin_root / ".codex-plugin" / "plugin.json"),
    }


def main():
    parser = argparse.ArgumentParser(description="Publish engineering-assistant as a Codex-recognizable local plugin.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--publish-root")
    parser.add_argument("--marketplace-path")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    config = load_config(repo_root / args.config if not Path(args.config).is_absolute() else Path(args.config))
    publish_root = expand(args.publish_root) if args.publish_root else None
    marketplace_path = expand(args.marketplace_path) if args.marketplace_path else None
    print(json.dumps(publish(repo_root, config, publish_root, marketplace_path), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
