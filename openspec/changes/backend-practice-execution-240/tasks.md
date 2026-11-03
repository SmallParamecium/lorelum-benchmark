## 1. Proposal gate

- [x] 1.1 创建 Issue #240 并记录范围、依赖与验收。
- [x] 1.2 OpenSpec strict validation 通过并创建仅含规划的初始 PR #241。
- [x] 1.3 用户明确选择“确认实施”，已回写 Issue #240；不授权其他模型。

## 2. Measurement contract and fixtures

- [x] 2.1 冻结任务映射、四条件、公开/私有边界、失败分类与证据合同；见 private/experiment.json。
- [x] 2.2 实现12题 public starter 和 private 行为验收。
- [x] 2.3 每题完成 reference、等价解、错误实现、关键 mutation 与合法路径校准；r3共103/103符合预期，r1/r2失败证据保留。
- [x] 2.4 实测容器、跨 attempt、数据库及真实 canary 隔离；12项审计通过。

## 3. Delivery and execution

- [ ] 3.1 恢复 muse-spark-1.3 实际路由并验证精确身份；其他模型须用户先确认。
- [ ] 3.2 冻结 semantic query/get、B/D全文、版本和随机顺序；失败不静默替代。
- [ ] 3.3 完成四条件链路 smoke，保留原始证据，单独报告。
- [ ] 3.4 运行开发集72次，按冻结规则归因；必要修复另建 revision。
- [ ] 3.5 策略冻结后开封确认集并运行72次。

## 4. Verification and reporting

- [ ] 4.1 执行仓库 validate、实际运行 smoke 和双轮独立审查；审查模型同样受授权约束。
- [ ] 4.2 汇总计划分母、健康、功能、质量、任务族胜平负和风险。
- [ ] 4.3 提供无/有Practice原始回答、代码和验收对比；更新Pack证据索引，不夸大显著性。

当前阻断：三个已配置服务通道均不提供可用的 Muse 路由；未调用其他模型。B/D全文和query已冻结，但C实际semantic检索尚未执行；另一个embedding模型未获授权。模型工作区/交付链路与双轮独立审查不得以应用容器离线校准替代。
