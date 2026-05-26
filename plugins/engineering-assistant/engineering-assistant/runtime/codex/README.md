# Codex Runtime Policy Pack

这些文件是给目标业务项目复制启用的运行时策略模板。插件目录只提供模板，不直接替目标项目写入 `.codex/` 或 `AGENTS.md`。

## 文件
- `config.toml`：推荐的 Codex 沙箱、审批和 profile 配置。
- `rules/default.rules`：高风险命令规则模板。
- `hooks/pre_tool_use_policy.py`：PreToolUse 命令守卫模板。

## 使用方式
1. 将本目录内容复制到目标项目 `.codex/`。
2. 按项目真实构建、测试、发布流程调整规则。
3. 将任务运行产物写入目标项目 `artifacts/_control/`。
4. 不要把插件目录作为 `--root` 传给控制面脚本。
