# framework-selection-standard

## 技术选型边界
- FW1 技术选型必须在概要设计、详细设计或项目 profile 中明确；缺失时必须主动询问用户，不得自行选择。
- FW2 选型范围覆盖后端框架、持久化框架、前端技术栈、组件库、中间件、测试框架、构建工具、可观测性和部署方式。
- FW3 Java/Spring 后端默认持久化框架建议为 `mybatis-plus`；直接使用 JDBC 必须有明确项目约束、历史兼容原因或评审批准。
- FW4 代码生成必须优先遵循现有仓库技术栈、依赖、目录结构、mapper/repository/service 分层和测试框架。
- FW5 框架替换、绕过现有 mapper/repository 模式、直接 SQL/JDBC 绕过团队默认框架时必须进入设计评审和代码评审 blocker 检查。

## 主动询问
- FW6 当 repo_context 无法识别持久化框架、Web 框架、前端技术栈、组件库、测试框架或构建工具时，必须主动询问用户。
- FW7 用户确认后的技术选型必须写回 `StageRunRequest.context.technology_selection`，并进入实现总结和设计到代码映射。
