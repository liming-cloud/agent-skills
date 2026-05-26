# Repo Context Miner 阶段指引

检查项：
- 识别 controller/service/domain/mapper/repository 等现有分层结构
- 梳理已有接口、DTO、异常码、返回结构和权限控制方式
- 梳理已有表结构、Mapper、SQL、索引和事务边界使用方式
- 梳理 Redis key、MQ exchange/routingKey/queue、定时任务和外部依赖
- 识别可复用 service、工具类、领域能力和禁止改动边界
- 输出本次需求的代码影响范围、风险点和待确认问题
