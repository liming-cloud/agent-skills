# team-adaptation-standard

## 团队适配边界
- TA1 本插件是人人取/萤启团队适配插件，默认 profile 为 `rrq-yq-team`，插件包名为 `teamwork-engineering-assistant`，不得与通用 `engineering-assistant` 发布包混用。
- TA2 执行任何阶段前必须加载 `engineering-assistant/registry/team-rule-catalog.yaml`、`engineering-assistant/registry/team-standard-sources.yaml` 和项目 profile；缺失时必须作为运行阻断或待补充信息处理。
- TA3 规范结论必须引用稳定 `rule_id`，优先使用 RRQ、YAPI、YQ、R、M、DB、E、P、A、H、D、I、FE、FW 前缀规则。
- TA4 MrDoc 导出的 HTML 只作为本插件规则内化的来源记录，不作为目标项目 workflow 的 agent 事实输入；目标项目运行时应读取 Markdown、JSON、YAML、代码和 control-plane 产物。

## 人人取/萤启必读规范
- RRQ-ARCH1 概要设计和详细设计必须明确人人取 SaaS/萤启服务商系统的系统边界、领域边界、事件协作、最终一致性和异常流。
- YAPI1-YAPI6 接口设计必须遵守 YApi 分组、Project 命名、模块/接口命名、路径、字段、响应结构、错误码、JSR303 注解和接口描述规范。
- RRQ-IDEMP1-RRQ-IDEMP3 核心写场景、外部回调、MQ 消费和表单提交必须说明幂等标识、去重窗口、存储介质、TTL、乱序处理和重复处理结果。
- RRQ-LOG1、RRQ-SEC1、RRQ-OBS1 要求日志上下文、敏感信息脱敏、关键路径埋点和系统级业务监控进入设计与自测证据。
- YQ1-YQ4 要求萤启服务商系统错误编码、错误码段、系统交互流向和合作加盟服务 MQ 场景按照 profile/repo_context 落地。

## Codex App 发布
- CAP1 发布脚本必须支持 `.codex-plugin/plugin.json`、`skills/`、`engineering-assistant/` 三段式插件包。
- CAP2 personal marketplace 布局必须发布到 `~/plugins/teamwork-engineering-assistant` 并写入 `~/.agents/plugins/marketplace.json`，marketplace entry 的 `source.path` 为 `./plugins/teamwork-engineering-assistant`。
- CAP3 local-root 布局默认发布到 `~/.codex/local-plugins/local-teamwork-engineering/plugins/teamwork-engineering-assistant`，不得写入仓库内 `plugins/` 目录。
