# AGENTS.md

## 仓库目标
- 本仓库维护 `engineering-assistant` 插件的源码、治理资产、skills 和发布镜像。
- `skills/` 是可触发能力源树，`engineering-assistant/` 是治理与运行时资产，`plugins/engineering-assistant/` 是发布镜像。

## 修改规则
- 优先修改 `generate_engineering_assistant_assets.py` 和回归测试，再运行生成器刷新源树与插件镜像。
- 不直接手补 `plugins/engineering-assistant/`，除非同一变更也进入生成器或源树。
- 所有任务控制产物写入目标项目 `artifacts/_control/`，不得写入插件目录。

## 验证要求
- 变更后运行 `python3 -m unittest discover -s tests -v`。
- 运行 `validate_skill_contract.py`、`validate_workflow.py`、`run_skill_evals.py` 和 `validate_skill_metadata.py`。
- 源树和插件镜像必须保持同步，除根级 `AGENTS.md` 外不得出现未解释差异。

## 风险边界
- 高风险动作、生产动作、发布、删除历史和范围外实现必须人工确认。
- 失败门禁不能被口头说明替代，必须修复或明确标记为 blocked / waiting_for_human_review。
