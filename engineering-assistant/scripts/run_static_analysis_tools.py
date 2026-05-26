#!/usr/bin/env python3
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

MASK = re.compile(r"(?i)(token|password|passwd|secret|key|credential|authorization)=([^\s&]+)")


def redact(text: str) -> str:
    return MASK.sub(lambda m: f"{m.group(1)}=***", text or "")


def run_cmd(cmd, cwd: Path, timeout: int, env=None):
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        return {
            "exit_code": proc.returncode,
            "duration_seconds": round(time.time() - started, 2),
            "output": redact(proc.stdout)[-12000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": 124,
            "duration_seconds": round(time.time() - started, 2),
            "output": redact((exc.stdout or "") + "\nTIMEOUT"),
        }


def download(url: str, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as response:
        target.write_bytes(response.read())
    return target


def discover(root: Path):
    return {
        "sonar_project": [str(p.relative_to(root)) for p in root.rglob("sonar-project.properties")],
        "qodana": [str(p.relative_to(root)) for p in list(root.rglob("qodana.yaml")) + list(root.rglob("qodana.yml"))],
        "checkstyle": [str(p.relative_to(root)) for p in list(root.rglob("checkstyle.xml")) + list(root.rglob("config/checkstyle/checkstyle.xml"))],
        "java_files": [str(p.relative_to(root)) for p in root.rglob("*.java") if "/target/" not in str(p)],
        "pom": [str(p.relative_to(root)) for p in root.rglob("pom.xml")],
        "gradle": [str(p.relative_to(root)) for p in list(root.rglob("build.gradle")) + list(root.rglob("build.gradle.kts"))],
    }


def find_executable(name: str):
    path = shutil.which(name)
    return str(Path(path).resolve()) if path else None


def ensure_checkstyle(args, tool_dir: Path, result: dict):
    existing = find_executable("checkstyle")
    if existing:
        return existing
    jars = sorted(tool_dir.glob("checkstyle-*-all.jar"))
    if jars:
        return str(jars[-1])
    if not args.allow_download:
        result["status"] = "tool_unavailable"
        result["reason"] = "checkstyle 未安装；如需下载官方 all.jar，请传 --allow-download"
        return None
    version = args.checkstyle_version
    url = args.checkstyle_url or f"https://github.com/checkstyle/checkstyle/releases/download/checkstyle-{version}/checkstyle-{version}-all.jar"
    try:
        return str(download(url, tool_dir / f"checkstyle-{version}-all.jar"))
    except Exception as exc:
        result["status"] = "download_failed"
        result["reason"] = redact(str(exc))
        result["download_url"] = url
        return None


def ensure_sonar(args, tool_dir: Path, result: dict):
    existing = find_executable("sonar-scanner")
    if existing:
        return existing
    candidates = sorted(tool_dir.rglob("sonar-scanner"))
    if candidates:
        return str(candidates[-1])
    if not args.allow_download:
        result["status"] = "tool_unavailable"
        result["reason"] = "sonar-scanner 未安装；如需下载 SonarScanner CLI，请传 --allow-download 和 --sonar-scanner-url"
        return None
    if not args.sonar_scanner_url:
        result["status"] = "missing_input"
        result["reason"] = "SonarScanner CLI 官方下载链接随版本和平台变化，必须通过 --sonar-scanner-url 或 SONAR_SCANNER_URL 提供"
        result["platform"] = {"system": platform.system(), "machine": platform.machine()}
        return None
    try:
        archive = download(args.sonar_scanner_url, tool_dir / "sonar-scanner-cli.zip")
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tool_dir)
        candidates = sorted(tool_dir.rglob("sonar-scanner"))
        return str(candidates[-1]) if candidates else None
    except Exception as exc:
        result["status"] = "download_failed"
        result["reason"] = redact(str(exc))
        return None


def ensure_qodana(args, tool_dir: Path, result: dict):
    existing = find_executable("qodana")
    if existing:
        return existing
    go_bin = Path.home() / "go" / "bin" / "qodana"
    if go_bin.exists():
        return str(go_bin)
    if not args.allow_download:
        result["status"] = "tool_unavailable"
        result["reason"] = "qodana CLI 未安装；如需按 JetBrains 官方方式安装，请传 --allow-download 且本机需有 go"
        return None
    if not find_executable("go"):
        result["status"] = "tool_unavailable"
        result["reason"] = "qodana CLI 可通过 go install 安装，但本机未发现 go"
        return None
    install = run_cmd(["go", "install", "github.com/JetBrains/qodana-cli@latest"], Path.cwd(), args.timeout_seconds)
    result["install"] = install
    return str(go_bin) if go_bin.exists() else None


def run_checkstyle(args, root: Path, output: Path, discovered: dict):
    result = {"name": "checkstyle", "status": "not_run"}
    config = args.checkstyle_config
    if not config:
        for item in ["checkstyle.xml", "config/checkstyle/checkstyle.xml"]:
            if (root / item).exists():
                config = item
                break
    if not config:
        result.update({"status": "missing_config", "reason": "未发现项目 checkstyle.xml；未使用临时 google/sun 基线替代团队规则"})
        return result
    if not discovered["java_files"]:
        result.update({"status": "not_applicable", "reason": "未发现 Java 文件"})
        return result
    tool = ensure_checkstyle(args, output / "_tools", result)
    if not tool:
        return result
    xml = output / "checkstyle-result.xml"
    targets = [str(root / "src/main/java")] if (root / "src/main/java").exists() else [str(root / p) for p in discovered["java_files"][:500]]
    if tool.endswith(".jar"):
        cmd = ["java", "-jar", tool, "-c", config, "-f", "xml", "-o", str(xml), *targets]
    else:
        cmd = [tool, "-c", config, "-f", "xml", "-o", str(xml), *targets]
    execution = run_cmd(cmd, root, args.timeout_seconds)
    result.update({"status": "passed" if execution["exit_code"] == 0 else "failed", "config": config, "result_file": str(xml), "execution": execution})
    return result


def run_sonar(args, root: Path, output: Path, discovered: dict):
    result = {"name": "sonar", "status": "not_run"}
    has_config = bool(discovered["sonar_project"])
    has_connection = bool(args.sonar_host_url or os.environ.get("SONAR_HOST_URL") or os.environ.get("SONAR_TOKEN"))
    if not has_config and not has_connection:
        result.update({"status": "missing_input", "reason": "缺少 sonar-project.properties 或 sonar.host.url/token，不能执行 SonarScanner"})
        return result
    tool = ensure_sonar(args, output / "_tools", result)
    if not tool:
        return result
    env = os.environ.copy()
    if args.sonar_host_url:
        env["SONAR_HOST_URL"] = args.sonar_host_url
    cmd = [tool, f"-Dsonar.projectBaseDir={root}", f"-Dsonar.scanner.metadataFilePath={output / 'sonar-report-task.txt'}"]
    execution = run_cmd(cmd, root, args.timeout_seconds, env=env)
    result.update({"status": "passed" if execution["exit_code"] == 0 else "failed", "execution": execution, "metadata_file": str(output / "sonar-report-task.txt")})
    return result


def run_qodana(args, root: Path, output: Path, discovered: dict):
    result = {"name": "qodana", "status": "not_run"}
    if not discovered["qodana"] and not args.qodana_linter:
        result.update({"status": "missing_config", "reason": "未发现 qodana.yaml；如需无配置运行，请显式指定 --qodana-linter"})
        return result
    tool = ensure_qodana(args, output / "_tools", result)
    if not tool:
        return result
    result_dir = output / "qodana"
    cmd = [tool, "scan", "--results-dir", str(result_dir)]
    if args.qodana_linter:
        cmd.extend(["--linter", args.qodana_linter])
    if args.qodana_native:
        cmd.append("--within-docker=false")
    execution = run_cmd(cmd, root, args.timeout_seconds)
    result.update({"status": "passed" if execution["exit_code"] == 0 else "failed", "result_dir": str(result_dir), "execution": execution})
    return result


def write_markdown(path: Path, report: dict):
    lines = [
        "# 静态分析工具执行报告",
        "",
        f"- root: `{report['root']}`",
        f"- generated_at: `{report['generated_at']}`",
        "",
        "## 工具状态",
    ]
    for tool in report["tools"]:
        lines.append(f"- {tool['name']}: {tool['status']} {tool.get('reason', '')}")
    lines.extend(["", "## 发现配置", ""])
    for key, value in report["discovered"].items():
        lines.append(f"- {key}: {len(value)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run SonarScanner, Qodana and Checkstyle with auditable fallback states.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="artifacts/code-quality-governor")
    parser.add_argument("--tools", default="sonar,qodana,checkstyle")
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--sonar-host-url", default=os.environ.get("SONAR_HOST_URL", ""))
    parser.add_argument("--sonar-scanner-url", default=os.environ.get("SONAR_SCANNER_URL", ""))
    parser.add_argument("--qodana-linter", default="")
    parser.add_argument("--qodana-native", action="store_true")
    parser.add_argument("--checkstyle-config", default="")
    parser.add_argument("--checkstyle-version", default="13.4.2")
    parser.add_argument("--checkstyle-url", default="")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    discovered = discover(root)
    selected = {item.strip().lower() for item in args.tools.split(",") if item.strip()}
    tools = []
    if "sonar" in selected or "sonar-scanner" in selected:
        tools.append(run_sonar(args, root, output, discovered))
    if "qodana" in selected:
        tools.append(run_qodana(args, root, output, discovered))
    if "checkstyle" in selected:
        tools.append(run_checkstyle(args, root, output, discovered))
    summary = {}
    for tool in tools:
        summary[tool["status"]] = summary.get(tool["status"], 0) + 1
    report = {
        "root": str(root),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "allow_download": args.allow_download,
        "discovered": discovered,
        "tools": tools,
        "summary": summary,
    }
    (output / "static-analysis-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "tool-run-summary.json").write_text(json.dumps({"tools": tools, "summary": summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(output / "static-analysis-report.md", report)
    print(json.dumps({"output": str(output), "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
