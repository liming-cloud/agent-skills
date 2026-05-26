# coding-standard

## 代码实现
- 代码变更必须保持最小必要范围，能映射到设计，具备测试和可观测性，不夹带无关重构。
- 项目定制功能不能破坏原有通用能力，新增模块边界和兼容策略必须在设计和实现摘要中说明。
- 注释必须解释业务约束、设计映射、风险原因或非显然实现；禁止用注释复述语法和显然赋值。

## 高质量代码定义
- CQ1 好代码必须同时满足正确性、领域表达、边界清晰、可测试、可维护、安全、可观测、性能并发可控和可演进；不能只以“功能跑通”作为完成标准。
- CQ2 代码必须能映射到需求、设计文档、接口契约和测试证据；无法映射的实现视为无设计依据。
- CQ3 复杂度必须服务业务，禁止 God Service、Anemic Domain、Utility Dumping、Framework Leakage 和 Pattern Hunting。

## JDK 21
- JDK1 `record` 用于不可变 DTO、命令对象、查询结果和值对象候选；不得用于持久化 PO 或需要复杂行为的聚合根。
- JDK2 `sealed class/interface` 用于有限状态或有限结果类型，必须配合穷尽分支和测试。
- JDK3 pattern matching switch 可用于有限类型/状态分派，复杂业务逻辑不得堆在 switch 分支内。
- JDK4 virtual thread 只用于受控阻塞 IO 并发；不得用于 CPU 密集任务提速，不得绕过连接池、限流、超时和背压。
- JDK5 禁止未经评审启用 preview feature 作为生产实现。
- JDK6 `Optional` 只用于返回可能不存在的结果，禁止作为字段、方法参数和序列化 DTO 字段。
- JDK7 Stream 只用于清晰的数据转换；复杂业务分支、审计上下文、异常处理优先使用显式循环和小方法。
- JDK8 金额、成本使用 `BigDecimal` 或明确精度模型；事实时间使用 `Instant`，展示层再转换时区。

## DDD
- DDD1 `domain` 层承载聚合、实体、值对象、领域服务、领域事件和业务不变量，禁止依赖 Spring、MyBatis-Plus、Redis、MQ、Sa-Token、Spring AI。
- DDD2 `application` 层负责编排用例、事务边界、权限上下文和端口调用，禁止沉淀复杂业务规则或直接依赖 mapper/SDK。
- DDD3 adapter 实现 port，框架类型、PO、SDK response 不得泄漏到 application/domain。
- DDD4 一个 application use case 默认只修改一个聚合；跨聚合协作用领域事件、outbox、本地消息表或显式补偿。
- DDD5 聚合根必须维护聚合内不变量；值对象必须不可变并在创建时校验。
- DDD6 Repository port 返回 domain model 或专用快照，不返回 MyBatis-Plus PO。
- DDD7 领域事件使用过去式命名，必须包含 tenantId、业务 ID、版本或时间戳、traceId。

## TDD
- TDD1 代码研发必须遵循测试清单、失败测试、最小实现、重构、补异常路径的节奏。
- TDD2 domain unit test 覆盖聚合不变量、值对象校验、状态机和领域服务。
- TDD3 application use case test 覆盖权限、事务编排、端口交互和异常码；只 mock 外部端口，不 mock 领域模型。
- TDD4 adapter integration test 覆盖 MyBatis-Plus SQL、Redis、MQ、Spring AI adapter；依赖真实容器或明确 fake，并保留真实环境验收任务。
- TDD5 测试必须有明确断言，禁止无断言测试、顺序依赖、真实 sleep 和外部公网不稳定依赖。
- TDD6 每个 bug 修复必须先补失败测试或复现脚本。

## 框架高级特性
- FWU1 Spring `@ConfigurationProperties` 必须配合校验集中管理配置，禁止散落读取环境变量。
- FWU2 `@Transactional` 只放在 application use case 或专用事务服务，不放在 Controller、mapper 和 private 方法。
- FWU3 MyBatis-Plus 只在 persistence adapter 使用，QueryWrapper/LambdaQueryWrapper 不得进入 application/domain。
- FWU4 Sa-Token 只通过 session port、actor provider 和权限桥接适配，业务层不直接调用 Sa-Token API。
- FWU5 Spring AI 类型只允许出现在 Spring AI adapter/infra 模块；ChatClient、Advisor、RAG、Tool Calling 按 Spring AI 专项规范执行。
- FWU6 Spring Cloud Stream/RocketMQ 消息必须有 messageId、tenantId、traceId、eventTime、version、幂等、重试和死信策略。
- FWU7 Redis key 必须登记 key registry，包含用途、TTL、value schema 和失效策略。

## 设计模式
- DP1 Strategy 只用于模型供应商路由、租户套餐、工具授权等真实变化点；禁止为两个 if 分支过早抽象。
- DP2 Factory 用于聚合创建、模型 client 创建、工具实例构建，并必须承担不变量或配置校验。
- DP3 Adapter/Port 用于隔离外部框架和基础设施；adapter 不得泄露框架类型。
- DP4 Specification 用于权限、配额和领域条件组合；不得把 SQL 拼接伪装成领域规则。
- DP5 State 用于 Agent run、租户生命周期、导入任务等明确状态机；状态简单时不要引入复杂类层级。
- DP6 Chain/Advisor 用于 AI advisor、安全、审计、策略链；顺序必须显式并有测试。
- DP7 Builder 只用于复杂不可变配置，不得允许半成品对象绕过必填校验。

## 接口与接口文档
- I1 路径遵循 `/api/v1`、`/service/v1`、`/console`、`/tapi/v1`、`/mapi`。
- I2 接口必须有充分业务理由，禁止 API 简单封装 DB CRUD。
- I3 一个接口只负责一个业务功能，禁止随意加参数或合并职责不同接口。
- I4 请求/响应字段使用小写驼峰，禁止拼音和无意义缩写。
- I5 响应结构为 `header.code/header.message/body`。
- I6 接口文档平台包含接口用途、适用场景、权限要求、注意事项、错误码。
- I7 入参/返回参数必须有 JSR303/Javadoc 注解，必填字段使用 `@NotBlank/@NotNull`。
- I8 废弃接口标注废弃时间、原因、替代接口。

## 异常
- E1 异常编码格式为 `[系统]-[服务]-[模块]-[错误码]`。
- E2 系统编码和服务编码由项目 profile 或 repo_context 注入，错误码必须按服务归属选择。
- E3 错误码范围：业务1000、参数2000、数据库3000、第三方4000、权限5000、状态6000、网络7000、系统8000、未知9000。
- E4 异常包含位置、原因、建议；禁止硬编码错误消息。
- E5 禁止空 catch、只打印不抛、重复打印日志、用异常控制业务流程。
- E6 业务异常 INFO 不打堆栈，系统异常 ERROR 打堆栈，第三方异常 WARN 保留上下文。
- E7 异常日志必须包含 TraceId，敏感信息不得进入异常消息或日志。

## 幂等与并发
- P1 修改核心数据接口必须评估幂等，尤其支付、订单、库存、回调、MQ 消费、表单提交。
- P2 幂等依据可用全量请求体 hash 或关键业务字段排序 hash。
- P3 Redis 幂等使用 `SETNX + TTL`；MQ 幂等使用 `messageId/业务唯一键 + Redis或DB记录`。
- P4 最终一致性只处理最新消息，旧消息基于时间戳/版本号丢弃。
- P5 高竞争写使用悲观锁，低冲突场景使用乐观锁/version。
- P6 分布式锁必须有超时时间和兜底方案。

## 注释与可读性
- CMT1 对外 API、DTO、application port、domain service、MQ message、Redis key registry、数据库迁移必须说明业务用途、权限/租户边界、错误语义和设计来源。
- CMT2 Java 使用 Javadoc 描述公开类型和非显然方法契约；TypeScript 使用 TSDoc 描述共享类型、hook、query key、表单 schema 和跨页面复用组件。
- CMT3 复杂状态机、幂等、补偿、重试、限流、缓存一致性、权限判断和安全处理必须在代码附近留下简短注释，并引用设计文档编号或任务编号。
- CMT4 禁止冗余注释、过期注释、与代码矛盾的注释、无 owner 的 TODO/FIXME。TODO/FIXME 必须包含任务编号、原因和关闭条件。
- CMT5 SQL DDL 必须使用表注释、关键字段注释和索引用途说明；禁止无用途字段、无用途索引和含糊命名。
- CMT6 注释、日志、示例和测试数据不得包含真实密钥、token、手机号、邮箱、客户数据或可反推生产环境的信息。
- CMT7 生成代码、适配器封装和临时兼容层必须声明生成来源或生命周期；临时兼容层必须有删除条件。
