# required-information-checklist

- [ ] QIN1 缺失信息已先尝试从仓库、上游产物、profile 和上下文获取
- [ ] QIN2 blocking 问题未回答时状态为 waiting_for_input
- [ ] QIN3 每个问题包含用途、原因、期望格式、示例和默认处理方式
- [ ] QIN4 问题集是当前阶段最小必要集合，按 critical/major/minor 排序
- [ ] QIN5 不重复询问可推导或已有来源的信息
- [ ] QIN6 用户补充信息会写回 context 或 artifact index
- [ ] QIN7 高风险、审批、生产变更、跨系统边界信息缺失时未使用假设绕过
- [ ] QIN8 optional 信息以 assumptions 或 optional question 记录
- [ ] QIN9 required-information 请求只作为 run artifact
- [ ] QIN10 下游 workflow 在 waiting_for_input 时暂停
