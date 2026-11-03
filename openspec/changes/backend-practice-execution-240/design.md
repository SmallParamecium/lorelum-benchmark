## Context

关联 Issue #240。已有21题文字对照 baseline 41/42，无法证明执行增益。本 change 只建立探索性执行证据，不代表整个 Pack 有效。来源方案为 packs 仓库 fixtures/backend-fundamentals/effectiveness-repair-plan-2026-11-03.md。

## Decisions

1. 六族各两题：唯一键、事件去重与本地效果、目标资源授权、关联批量读取、连接失败清理、滚动迁移。每族一个开发变体、一个封存变体。任务给公开合同和可发现事实，不提示解决步骤。
2. PostgreSQL 17.6，镜像 digest sha256:00bc86618629af00d2937fdc5a5d63db3ff8450acf52f0636ec813c7f4902929。并发用 barrier，故障用显式注入点，不用 sleep 作为竞争保证。连接取消与旧调用方兼容必须真实执行。
3. 每题 reference、不同结构等价解、starter、各关键断言单点 mutation。合法路径覆盖不同键、独立事件、合法共享、完整分页、合法长任务、满足条件后的退役。性能只有公开 SLO 才是 hard gate。
4. A 无指导；B 预定相关全文；C 独立控制面真实 semantic Top-3 query/get 冻结全文；D 无关且无危险指导，记录长度差异。semantic 失败保留 delivery failure，不自动 fallback keyword。query 从公开任务生成，不含 oracle 或目标 ID。
5. 独立会话、工作区、数据库与凭据；容器只见 public 和条件输入，不挂父仓库、历史或 private。联网策略仅允许声明的模型通道；canary 实测跨 attempt、宿主和隐藏验收不可读。evaluator 不接收组别或 Practice。
6. 仅 muse-spark-1.3；禁止自动替代。先验证精确返回模型身份和无工具连通，再允许成效调用。当前 lorelum 凭据返回503、openai 凭据返回404；两种 API 均失败。恢复必须有真实服务响应，不能仅改显示名。
7. 四条件链路 smoke 与统计分离。开发6题各条件3次共72次；封存6题同样72次，仅策略冻结后开封。随机运行顺序，重复不是独立任务。重试仅传输/基础设施原因且保留全部记录。
8. execution health、semantic、quality 独立报告。保留计划分母、失败原因、原始回答、候选代码、验收命令/输出/状态、检索候选、全文 digest、模型/运行时版本、输入 hash 和耗时/token。
9. 内容保持V0，只有实际失败证实内容缺口才另建V1。评分变化全条件重跑。至少两个任务族B对A可复现改善且无严重回归才值得扩展；不是统计显著性结论。报告给双方原文与执行差异，无增益同样展示。

## Non-goals

不发布正式 suite/record，不改变 React 专属条件，不以12题概括21条，不为求正结果换模型或筛失败题，不自动合并 PR。

## Implementation gate

初始 PR 仅 OpenSpec；strict validation 后向用户展示范围、预期、验证、非目标并获确认才开始实现。确认不包含其他模型授权。任务校准与隔离未通过前不运行成效模型。最终按仓库规定执行验证与双轮独立审查；未获模型审查授权不得调用其他模型来审查。
