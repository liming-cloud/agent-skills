# required-information-standard

## 主动询问边界
- QIN1 必填信息缺失且无法通过仓库、上游产物、profile 或已确认上下文可靠推导时，skill 必须主动询问用户，不得继续伪造结论。
- QIN2 主动询问必须区分 blocking 与 optional；blocking 问题未回答时，`StageRunResult.status` 必须为 `waiting_for_input`。
- QIN3 每个问题必须说明用途、阻断原因、期望格式、示例和默认处理方式，避免用户不知道如何回答。

## 问题组织
- QIN4 一次询问只返回完成当前阶段所需的最小必要问题集，按 `critical`、`major`、`minor` 排序。
- QIN5 不重复询问可从仓库、上游产物或 profile 中可靠获得的信息；引用来源即可。
- QIN6 用户补充信息后必须写回 `StageRunRequest.context` 或 artifact index，并保留来源和时间。
- QIN11 blocking `required_information_requests` 或 `waiting_for_human_review` 必须同时生成面向人工的 HTML 审阅包；聊天提示只能作为摘要，不能作为唯一人工输入界面。
- QIN12 HTML 审阅包必须包含每个待确认项的可编辑输入控件、问题 id 或稳定序号、人工审阅人/决策字段，以及可复制或下载的结构化答案 JSON。
- QIN13 `StageRunResult.artifacts` 必须登记 HTML 审阅包路径；`validate_stage_run_result.py` 必须阻断缺失 HTML、HTML 不存在、或 HTML 不能填写/导出答案的运行结果。
- QIN14 人工审阅 HTML 必须集中放在目标项目 `docs/human-review/` 目录；agent 只消费 MD/JSON/YAML 作为事实来源，不得把 HTML 作为设计、需求或审批事实输入，只允许校验器检查 HTML 是否存在、可填写、可导出。

## 风险约束
- QIN7 涉及高风险动作、审批、生产变更、跨系统边界、数据一致性或安全权限的信息缺失时，不允许以假设绕过人工确认。
- QIN8 可用合理假设继续的非 blocking 信息，必须在 assumptions 中标注，并生成 optional 问题供用户补充。
- QIN9 required-information 请求不是正式留存文档，只作为 run artifact 和 workflow 恢复依据。
- QIN10 下游 skill 接收到 `waiting_for_input` 状态时必须暂停，直到 blocking 问题被回答或人工明确取消。
