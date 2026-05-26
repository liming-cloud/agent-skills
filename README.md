# agent-skills

本仓库维护 `engineering-assistant` 插件的源码、治理资产、skills 和发布镜像。

## 目录边界

- `skills/`：可触发 skill 源树，包含 `SKILL.md`、`contract.yaml`、`output.schema.json`、eval 和 workflow node。
- `engineering-assistant/`：治理与运行时资产，包含 standards、schemas、scripts、workflows、registry、runtime policy、compiled skill IR 和 eval fixtures。
- `plugins/engineering-assistant/`：Codex 插件发布镜像，由生成器同步生成，禁止直接手补。

## 修改方式

优先修改 `generate_engineering_assistant_assets.py` 和回归测试，然后运行：

```bash
python3 generate_engineering_assistant_assets.py
```

生成器会刷新 `skills/`、`engineering-assistant/` 和 `plugins/engineering-assistant/`。新增运行时能力也必须进入生成器、schema、测试和插件镜像。

## 验证命令

```bash
PYTHONPYCACHEPREFIX=/private/tmp/agent-pycache python3 -m unittest discover -s tests -v
python3 engineering-assistant/scripts/validate_skill_contract.py skills/*/contract.yaml
python3 engineering-assistant/scripts/validate_workflow.py engineering-assistant/workflows/*.yaml
python3 engineering-assistant/scripts/run_skill_evals.py
python3 engineering-assistant/scripts/run_skill_evals.py --mode scored
python3 engineering-assistant/scripts/run_skill_evals.py --mode scored --no-write-report
python3 engineering-assistant/scripts/validate_skill_metadata.py
diff -qr skills plugins/engineering-assistant/skills
diff -qr engineering-assistant plugins/engineering-assistant/engineering-assistant
```

## 下游 canary

第一轮只读 canary 仓库：

`/Users/sunliming/work/project/personal/ai-platform-v1`

`engineering-assistant/evals/fixtures/ai-platform-v1.json` 记录允许读取的 workflow/control-plane 入口。`run_skill_evals.py --mode scored` 会验证 router、context pack 和插件镜像同步，不写入下游仓库。
