# Implementation Controller 阶段指引

检查项：
- 只接受已审批 Markdown/JSON/YAML 设计产物，HTML 仅作为人工审阅入口
- 所有 `_control` 产物写入目标项目 `artifacts/_control/`，不得写入插件目录
- implementation-contract.json 必须包含 allowed_modules、forbidden_modules、expected_interfaces、expected_services、expected_repositories_or_mappers、required_tests、architecture_rules、done_conditions、technology_adoption_contract
- quality-contract.json 必须包含 required_commands 和 required_evidence，缺失或占位命令必须阻断
- 必须生成 artifacts/_control/traceability-matrix.json 作为机读事实源，并生成 docs/human-readable/traceability-report.html 作为人工阅览入口；HTML 不得反向作为 agent 事实输入
- 普通实现范围、测试、lint、设计映射失败进入 review -> repair -> validate，最多 2 轮
- 业务决策、设计冲突、高风险动作、生产动作和修复轮次耗尽才进入人工审批
