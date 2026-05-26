#!/usr/bin/env python3
import argparse
import html
import re
from pathlib import Path


STYLE = """
body{margin:0;background:#f6f7f9;color:#16181d;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;line-height:1.65}
main{max-width:1080px;margin:0 auto;padding:40px 28px 72px}
article{background:#fff;border:1px solid #dde2ea;border-radius:8px;padding:32px;box-shadow:0 1px 2px rgba(15,23,42,.04)}
h1,h2,h3{line-height:1.25;color:#111827;margin:1.4em 0 .55em}
h1{font-size:30px;margin-top:0;border-bottom:1px solid #e5e7eb;padding-bottom:16px}
h2{font-size:22px}h3{font-size:18px}
p{margin:10px 0}ul,ol{padding-left:26px}li{margin:6px 0}
code{background:#f3f4f6;border:1px solid #e5e7eb;border-radius:4px;padding:1px 5px;font-size:.93em}
pre{background:#0f172a;color:#e5e7eb;border-radius:8px;padding:16px;overflow:auto}
pre code{background:transparent;border:0;padding:0;color:inherit}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:14px}
th,td{border:1px solid #d8dee9;padding:8px 10px;vertical-align:top}
th{background:#f1f5f9;text-align:left}
.meta{margin:0 0 18px;color:#4b5563;font-size:13px}
.notice{border:1px solid #f3c969;background:#fff8e6;border-radius:8px;padding:12px 14px;margin-bottom:18px;color:#5f4600}
"""


def inline_markup(value: str) -> str:
    escaped = html.escape(value)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


def table_to_html(rows):
    output = ["<table>"]
    for idx, row in enumerate(rows):
        tag = "th" if idx == 0 else "td"
        if idx == 1 and all(set(cell.strip()) <= {"-", ":"} for cell in row):
            continue
        output.append("<tr>" + "".join(f"<{tag}>{inline_markup(cell.strip())}</{tag}>" for cell in row) + "</tr>")
    output.append("</table>")
    return "\n".join(output)


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    blocks = []
    paragraph = []
    list_open = False
    code_open = False
    code_lines = []
    table_rows = []

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            blocks.append("<p>" + inline_markup(" ".join(paragraph)) + "</p>")
            paragraph = []

    def flush_list():
        nonlocal list_open
        if list_open:
            blocks.append("</ul>")
            list_open = False

    def flush_table():
        nonlocal table_rows
        if table_rows:
            blocks.append(table_to_html(table_rows))
            table_rows = []

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("```"):
            flush_paragraph()
            flush_list()
            flush_table()
            if code_open:
                blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = []
                code_open = False
            else:
                code_open = True
            continue
        if code_open:
            code_lines.append(line)
            continue
        if not line.strip():
            flush_paragraph()
            flush_list()
            flush_table()
            continue
        if line.startswith("|") and line.endswith("|"):
            flush_paragraph()
            flush_list()
            table_rows.append(line.strip("|").split("|"))
            continue
        flush_table()
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            flush_list()
            level = min(len(heading.group(1)), 3)
            blocks.append(f"<h{level}>{inline_markup(heading.group(2))}</h{level}>")
            continue
        item = re.match(r"^\s*[-*]\s+(.+)$", line)
        if item:
            flush_paragraph()
            if not list_open:
                blocks.append("<ul>")
                list_open = True
            blocks.append("<li>" + inline_markup(item.group(1)) + "</li>")
            continue
        flush_list()
        paragraph.append(line.strip())

    flush_paragraph()
    flush_list()
    flush_table()
    if code_open:
        blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(blocks)


def render(source: Path, output_dir: Path, root: Path) -> Path:
    text = source.read_text(encoding="utf-8")
    title = source.stem
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    rel_source = source.relative_to(root) if source.is_absolute() and source.is_relative_to(root) else source
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / (source.stem + ".html")
    body = markdown_to_html(text)
    output.write_text(
        "<!doctype html>\n"
        "<html lang=\"zh-CN\">\n"
        "<head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{html.escape(title)}</title><style>{STYLE}</style></head>\n"
        "<body><main><article>"
        "<div class=\"notice\">Human-readable mirror. Agent source of truth is the Markdown/JSON/YAML artifact, not this HTML file.</div>"
        f"<p class=\"meta\">source: {html.escape(str(rel_source))}</p>"
        f"{body}</article></main></body></html>\n",
        encoding="utf-8",
    )
    return output


def main():
    parser = argparse.ArgumentParser(description="Render approved Markdown documents into read-only human HTML mirrors.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--output-dir", default="docs/human-readable")
    parser.add_argument("sources", nargs="+")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output_dir = root / args.output_dir
    for item in args.sources:
        source = Path(item)
        if not source.is_absolute():
            source = root / source
        if source.suffix.lower() != ".md":
            raise SystemExit(f"only Markdown sources are accepted: {source}")
        print(render(source.resolve(), output_dir, root))


if __name__ == "__main__":
    main()
