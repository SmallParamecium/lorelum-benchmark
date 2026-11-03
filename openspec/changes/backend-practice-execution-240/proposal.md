## Why

Issue #240：后端 Pack 的文字问答存在天花板，尚无可隔离、可校准的代码执行对照。需要消费者可见行为证据，而不是检索命中率或答案完整度。

## What Changes

- 在 incubator 增加12个真实 PostgreSQL 任务、私有行为验收和校准夹具。
- 增加四条件探索实验编排与不可变证据清单；不修改现有正式 record 枚举。
- 先校准和隔离，再执行开发集与封存确认集；模型仅限用户批准的 muse-spark-1.3。
- 当前 PR 初始阶段仅包含 OpenSpec；实现需用户明确确认。

## Capabilities

### New Capabilities

- `backend-execution-calibration`: 数据库任务行为验收、校准、隔离与条件独立证据要求。

### Modified Capabilities

- 无；任务特定选择保留在本 change design，不升级正式 suite 或改变既有协议。

## Impact

计划影响 incubator 后端候选及必要的版本化 runner helper。Pack 仓库仅保存检索 fixture、结果摘要和证据索引。不得改写历史结果或引入模型自动替换。关联 https://github.com/lorelum/lorelum-benchmark/issues/240 。
