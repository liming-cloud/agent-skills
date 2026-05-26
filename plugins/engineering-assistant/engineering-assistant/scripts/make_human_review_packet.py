#!/usr/bin/env python3
import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path


CONTROL_DIR = Path("artifacts/_control")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_target_project_root(root: Path) -> Path:
    root = root.resolve()
    plugin_markers = [
        root / ".codex-plugin" / "plugin.json",
        root / "engineering-assistant" / "scripts" / "make_human_review_packet.py",
        root / "skills" / "requirement-intake" / "SKILL.md",
    ]
    if any(marker.exists() for marker in plugin_markers):
        raise SystemExit("--root must be the target project root, not the Codex plugin directory")
    return root


def update_control_artifact_index(root: Path, name: str, path: Path, artifact_type: str, producer: str):
    control = root / CONTROL_DIR
    control.mkdir(parents=True, exist_ok=True)
    index_path = control / "artifact-index.json"
    data = read_json(index_path, {"artifacts": {}})
    rel = str(path.relative_to(root)) if path.is_absolute() else str(path)
    data["artifacts"][name] = {
        "name": name,
        "path": rel,
        "artifact_type": artifact_type,
        "producer": producer,
        "updated_at": now_iso(),
    }
    data["updated_at"] = now_iso()
    write_json(index_path, data)


def stable_question_id(request, request_index: int, question, question_index: int) -> str:
    for key in ("id", "question_id"):
        value = question.get(key) if isinstance(question, dict) else None
        if value:
            return str(value)
    request_id = request.get("id") or request.get("request_id") or f"RIR-{request_index + 1}"
    return f"{request_id}-Q{question_index + 1}"


def normalize_questions(stage_result: dict) -> list[dict]:
    normalized = []
    requests = stage_result.get("required_information_requests") or []
    for request_index, request in enumerate(requests):
        questions = request.get("questions") or []
        for question_index, question in enumerate(questions):
            if isinstance(question, str):
                question = {"question": question}
            question_id = stable_question_id(request, request_index, question, question_index)
            normalized.append({
                "request_id": request.get("id") or request.get("request_id") or f"RIR-{request_index + 1}",
                "question_id": question_id,
                "question": question.get("question", ""),
                "reason": question.get("reason") or request.get("reason", ""),
                "required": question.get("required", request.get("blocking", True)),
                "priority": question.get("priority") or request.get("priority", "major"),
                "expected_format": question.get("expected_format", ""),
                "example": question.get("example", ""),
            })
    return normalized


def stage_result_from_control(root: Path) -> dict:
    control = root / CONTROL_DIR
    task = read_json(control / "current-task.json", {})
    questions = read_json(control / "open-questions.json", {"questions": []})
    raw_questions = questions.get("questions", [])
    return {
        "stage": "control_review",
        "skill_id": "workflow-orchestrator",
        "status": "waiting_for_human_review",
        "trace": {"source": str(control)},
        "required_information_requests": [
            {
                "id": "CONTROL-OPEN-QUESTIONS",
                "blocking": True,
                "priority": "critical",
                "reason": "控制面存在待人工确认事项。",
                "questions": [
                    {"question": str(item), "expected_format": "填写确认结论、决策或补充信息"}
                    for item in raw_questions
                ],
            }
        ],
        "required_actions": task.get("required_actions", []),
    }


def script_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def render_review_packet(stage_result: dict, title: str) -> str:
    questions = normalize_questions(stage_result)
    escaped_title = html.escape(title)
    rows = []
    for item in questions:
        qid = html.escape(item["question_id"])
        rows.append(f"""
        <article class="question" data-question-id="{qid}" data-request-id="{html.escape(item['request_id'])}">
          <div class="question-head">
            <span class="pill">{html.escape(str(item['priority']))}</span>
            <span class="qid">{qid}</span>
          </div>
          <h3>{html.escape(item['question'])}</h3>
          <p><strong>用途/阻断原因：</strong>{html.escape(item['reason'] or '未提供')}</p>
          <p><strong>建议格式：</strong>{html.escape(item['expected_format'] or '自由文本')}</p>
          <label>人工确认结果
            <textarea data-answer-for="{qid}" rows="4" placeholder="请填写确认结论。"></textarea>
          </label>
          <label>证据或备注
            <textarea data-note-for="{qid}" rows="2" placeholder="可填写来源、约束、审批意见或暂不确认原因。"></textarea>
          </label>
        </article>
        """)

    if not rows:
        rows.append("<p>当前 StageRunResult 未提供 required_information_requests。</p>")

    writeback_targets = "\n".join(
        f"<li>{html.escape(str(item))}</li>"
        for item in stage_result.get("required_actions", [])
    ) or "<li>将答案回写到 StageRunRequest.context、artifact index 或对应阶段产物。</li>"

    return f"""<!doctype html>
<html lang="zh-CN" data-human-review-packet="required-information">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #fff;
      --text: #172033;
      --muted: #5f6978;
      --line: #d9dee7;
      --accent: #1f5fbf;
      --danger: #b42318;
      --soft: #eef5ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{ max-width: 1080px; margin: 0 auto; padding: 36px 24px 72px; }}
    header {{ border-bottom: 2px solid var(--line); margin-bottom: 22px; padding-bottom: 18px; }}
    h1, h2, h3 {{ line-height: 1.25; margin: 0; }}
    h1 {{ font-size: 30px; }}
    h2 {{ font-size: 20px; margin: 28px 0 12px; }}
    h3 {{ font-size: 17px; margin-top: 10px; }}
    p {{ margin: 8px 0; }}
    code {{ background: #eef1f5; border: 1px solid var(--line); border-radius: 4px; padding: 1px 5px; }}
    .meta, section, .question {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
      margin-top: 18px;
    }}
    .label {{ color: var(--muted); display: block; font-size: 12px; text-transform: uppercase; }}
    .value {{ font-weight: 650; }}
    .block {{ background: #fff4ed; border-color: #f3b8a6; }}
    .block strong {{ color: var(--danger); }}
    .question {{ margin: 12px 0; }}
    .question-head {{ display: flex; gap: 8px; align-items: center; color: var(--muted); }}
    .pill {{ background: var(--soft); border: 1px solid #c8dcff; border-radius: 999px; padding: 2px 8px; font-size: 12px; }}
    .qid {{ font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; }}
    label {{ display: block; margin-top: 12px; font-weight: 650; }}
    input, select, textarea {{
      width: 100%;
      margin-top: 6px;
      border: 1px solid #aeb8c6;
      border-radius: 6px;
      padding: 10px;
      font: inherit;
      background: #fbfcff;
      color: var(--text);
    }}
    textarea {{ resize: vertical; min-height: 68px; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }}
    button {{
      border: 1px solid #164d9f;
      background: var(--accent);
      color: #fff;
      border-radius: 6px;
      padding: 9px 12px;
      font-weight: 700;
      cursor: pointer;
    }}
    button.secondary {{ background: #fff; color: var(--accent); }}
    #answer-json {{ min-height: 220px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; }}
    .footer {{ color: var(--muted); font-size: 13px; margin-top: 20px; }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>{escaped_title}</h1>
    <p>本页用于人工填写阻断项。填写后点击“生成答案 JSON”，再复制或下载，交给研发助手回写到阶段输入和产物索引。</p>
    <div class="meta">
      <div><span class="label">Stage</span><span class="value">{html.escape(str(stage_result.get('stage', '')))}</span></div>
      <div><span class="label">Skill</span><span class="value">{html.escape(str(stage_result.get('skill_id', '')))}</span></div>
      <div><span class="label">Status</span><span class="value">{html.escape(str(stage_result.get('status', '')))}</span></div>
      <div><span class="label">Generated At</span><span class="value">{html.escape(now_iso())}</span></div>
    </div>
  </header>

  <section class="block">
    <h2>当前门禁</h2>
    <p><strong>存在人工输入或人工审阅阻断。</strong>在答案回写并重新校验前，不得继续进入后续研发阶段。</p>
  </section>

  <section>
    <h2>审阅人信息</h2>
    <label>审阅人
      <input id="reviewer-name" placeholder="姓名或角色">
    </label>
    <label>人工决策
      <select id="review-decision">
        <option value="answers_provided">已补充答案</option>
        <option value="approved">批准继续</option>
        <option value="rejected">拒绝继续</option>
        <option value="needs_more_input">仍需补充</option>
      </select>
    </label>
  </section>

  <section>
    <h2>待确认项</h2>
    {''.join(rows)}
  </section>

  <section>
    <h2>回写目标</h2>
    <ul>{writeback_targets}</ul>
  </section>

  <section>
    <h2>答案 JSON</h2>
    <div class="actions">
      <button type="button" onclick="renderAnswerJson()">生成答案 JSON</button>
      <button class="secondary" type="button" onclick="copyAnswerJson()">复制 JSON</button>
      <button class="secondary" type="button" onclick="downloadAnswerJson()">下载 JSON</button>
    </div>
    <textarea id="answer-json" readonly placeholder="生成后的结构化答案会出现在这里。"></textarea>
  </section>

  <p class="footer">HTML 面向人工填写；导出的 JSON 面向插件回写和 StageRunResult 恢复。</p>
</main>
<script id="stage-run-result" type="application/json">{script_json(stage_result)}</script>
<script>
function sourceData() {{
  return JSON.parse(document.getElementById('stage-run-result').textContent);
}}
function collectAnswers() {{
  const source = sourceData();
  const answers = Array.from(document.querySelectorAll('[data-question-id]')).map((node) => {{
    const questionId = node.getAttribute('data-question-id');
    const requestId = node.getAttribute('data-request-id');
    const answer = document.querySelector(`[data-answer-for="${{CSS.escape(questionId)}}"]`).value.trim();
    const note = document.querySelector(`[data-note-for="${{CSS.escape(questionId)}}"]`).value.trim();
    return {{ request_id: requestId, question_id: questionId, answer, note }};
  }});
  return {{
    packet_type: 'human_required_information_answers',
    generated_at: new Date().toISOString(),
    reviewer: {{
      name: document.getElementById('reviewer-name').value.trim(),
      decision: document.getElementById('review-decision').value
    }},
    source: {{
      stage: source.stage,
      skill_id: source.skill_id,
      status: source.status,
      trace: source.trace || {{}}
    }},
    answers,
    ready_for_writeback: answers.every((item) => item.answer.length > 0)
  }};
}}
function renderAnswerJson() {{
  document.getElementById('answer-json').value = JSON.stringify(collectAnswers(), null, 2);
}}
async function copyAnswerJson() {{
  renderAnswerJson();
  await navigator.clipboard.writeText(document.getElementById('answer-json').value);
}}
function downloadAnswerJson() {{
  renderAnswerJson();
  const blob = new Blob([document.getElementById('answer-json').value], {{ type: 'application/json' }});
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = 'human-required-information-answers.json';
  link.click();
  URL.revokeObjectURL(link.href);
}}
</script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Create an editable HTML human review packet.")
    parser.add_argument("--root", required=True, help="Target project root where the review packet will be written.")
    parser.add_argument("--stage-result", help="StageRunResult JSON containing required_information_requests.")
    parser.add_argument("--output", default="docs/human-review/final-review-packet.html")
    parser.add_argument("--title", default="Engineering Human Review Packet")
    parser.add_argument("--skip-index", action="store_true", help="Do not update artifacts/_control/artifact-index.json.")
    args = parser.parse_args()

    root = validate_target_project_root(Path(args.root))
    if args.stage_result:
        stage_result = read_json(Path(args.stage_result), {})
    else:
        stage_result = stage_result_from_control(root)

    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_review_packet(stage_result, args.title), encoding="utf-8")
    if not args.skip_index:
        update_control_artifact_index(root, output.name, output, "html", "make_human_review_packet")
    print(output)


if __name__ == "__main__":
    main()
