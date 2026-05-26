# detailed-design-standard

## 适用范围
适用于 `detailed-design` 阶段输出详细设计、专项规范、接口契约、测试策略和进入设计评审前的补充设计。

## 专项识别
- DD1 详细设计必须基于需求、概要设计、项目 profile 和 repo_context 主动识别专项规范；不能只生成通用 `detailed-design.md`。
- DD2 涉及租户、用户、成员、角色、权限、菜单、会话、认证、鉴权或多租户隔离时，必须生成 IAM/RBAC 专项规范。
- DD3 涉及 Spring AI、LLM provider、Embedding、VectorStore、RAG、Agent、Tool Calling、Prompt 模板、模型调用观测时，必须生成 Spring AI 专项规范。
- DD4 涉及当前仍在快速演进的外部框架时，必须核对官方文档或官方发布页，并在规范中记录来源和核对日期。

## IAM/RBAC 专项规范
- IAM1 产物名建议为 `identity-access-tenant-rbac-spec.md`，正式文档编号使用 `DDD-*`。
- IAM2 必须覆盖 Tenant、User、TenantMember、Role、Permission、RolePermission、Menu、Actor 的定义、归属 bounded context 和事实源。
- IAM3 必须覆盖核心表、关键字段、唯一约束、租户隔离字段、索引、状态机、事务边界、并发控制和审计。
- IAM4 必须覆盖首批权限字典、权限码格式、菜单派生规则、前端展示权限和后端强鉴权边界。
- IAM5 必须覆盖登录、`/auth/me`、成员、角色、角色权限、租户概要、审计查询等接口清单。
- IAM6 必须覆盖 Sa-Token Redis-backed session、权限缓存失效、跨租户防越权测试和 E2E 权限验证。

## Spring AI 专项规范
- SAI1 产物名建议为 `spring-ai-framework-spec.md`，正式文档编号使用 `DDD-*`。
- SAI2 必须明确生产版本基线、BOM 锁定策略、升级候选和禁止使用的 milestone/废弃 API。
- SAI3 必须隔离 Spring AI 类型；domain、application port、Controller DTO 不得暴露 `org.springframework.ai.*`。
- SAI4 必须覆盖 ChatClient、Advisor 顺序、RAG、Tool Calling、结构化输出、凭据、供应商适配、观测、审计、异常降级和测试策略。
- SAI5 Chat memory 必须有显式 conversationId 和租户隔离；禁止依赖默认或隐式会话 ID。
- SAI6 Tool Calling 只能暴露经 AgentVersion/ToolBinding 授权的工具，工具内部必须再次校验租户、权限、幂等和审计。
- SAI7 prompt/completion 默认不得进入日志或 trace；调试开启必须使用脱敏 profile。

## 文档治理与评审
- DD5 专项规范进入正式文档目录时，必须同步生成 `docs/human-readable/` HTML 阅览稿，HTML 标记为 human-only。
- DD6 新增专项规范后，当前设计评审结论必须失效或转为需重新评审；代码研发仍保持阻断，直到 design-review 覆盖新增规范并通过。
- DD7 `StageRunResult`、artifact index、workflow trace 和 design-review finding 必须登记新增专项规范，避免下游 agent 漏读。
