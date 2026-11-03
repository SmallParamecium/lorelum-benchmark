# Backend execution candidate v1

关联 [Issue #240](https://github.com/lorelum/lorelum-benchmark/issues/240)、[PR #241](https://github.com/lorelum/lorelum-benchmark/pull/241)。仅 incubator 探索，不是正式 suite、正式 record 或 Practice 有效性结论。

## 布局与边界

- `tasks/<family>-<variant>/public/task.md`：产品合同。
- `tasks/<family>-<variant>/public/starter/`：独立应用快照，仅这些源码可进入编码工作区。
- `private/definitions.py`：任务合同与 schema 来源。
- `private/implementations.py`、`mutations.py`：校准用 reference、不同结构等价解、starter 与单点错误；禁止交付模型。
- `private/evaluator.py`：只观察请求、响应、持久状态和数据库证据，不接收条件或 Practice。
- `private/engine.py`：隔离数据库、只读应用容器、有限资源、固定目标 ingress 和自动资源回收。
- `private/experiment.json`：四条件、完整 B/D 指导、来源 hash、离线 token 计数、预冻结 query、144 个计划 attempt。禁止复制到模型工作区。

每个 attempt 只挂载随机临时目录中的 `app.py` 和 `server.py`，不挂父仓库、`.git`、private 或历史结果。应用及数据库处于独立 internal 网络；宿主访问经双网卡 ingress 的两个固定 TCP 目标转发，不能指定外部目标。应用仅获本数据库普通 app 凭据；管理凭据仅在宿主控制面和数据库容器中。编码模型尚未运行；网络内执行器不是模型工具沙箱的替代证明。

## 十二题

| 族 | variant 1：开发 | variant 2：封存确认 | 主要行为证据 |
| --- | --- | --- | --- |
| unique | 精确 team handle | 邮箱大小写/空白归一 | 竞争写、不同键、原值、存储错误、重启 |
| event | claim 后中断丢效果 | 效果先提交后并发重投 | 并发、故障/取消恢复、独立事件、坏数据 |
| authorization | 原子批量更新 | 按项部分更新 | 跨 owner 拒绝、公开/共享/委托合法路径、混合目标 |
| relations | 完整子列表 | 每父项两条续页 | 数据/排序/租户等价、空父项、续页、公开SQL往返SLO |
| cleanup | 异常泄漏连接 | 归还未清理事务 | 持久成功、异常/取消回滚、后续请求、合法长任务 |
| migration | 非web旧调用方 | 回滚承诺 | 旧/新兼容、全调用方、并发inventory、数据保留、最终退役 |

两个变体在同族内相关，不得算作十二个跨领域独立样本。确认题的离线 oracle 校准不等于模型开封；确认模型结果仅在策略冻结后运行。

## 复现离线校准

宿主需要 Docker Linux 引擎、Python 及 `psycopg[binary]==3.2.10`。镜像固定 Python 3.12.11、typing-extensions 4.16.0、psycopg 3.2.10 与 PostgreSQL 17.6 digest；运行报告另记录构建镜像 ID。

```sh
docker build -t backend-execution-python:v1 -f incubator/practice-injection/backend-execution-v1/private/Dockerfile incubator/practice-injection/backend-execution-v1/private
python -B incubator/practice-injection/backend-execution-v1/private/run_calibration.py --workers 2 --output artifacts/backend-execution/calibration-unique-run-id.json
python -B incubator/practice-injection/backend-execution-v1/private/audit_isolation.py --output artifacts/backend-execution/isolation-unique-run-id.json
bun run validate
openspec validate backend-practice-execution-240 --strict
```

输出文件不得已存在；校准脚本拒绝覆盖。每个实现使用独立应用、网络、数据库和凭据，保留 HTTP 请求/响应、数据状态、每条断言、源码 hash 和执行健康。正确解必须通过，starter 必须行为失败，mutation 必须命中指定的拒绝检查。基础设施错误不是 mutation 被识别。SQL 往返由独立的 PostgreSQL `pg_stat_statements` 观察，不以候选自报计数作为唯一证据。确定性插入窗口使用数据库 advisory gate 并观察所有竞争会话进入等待后释放；不靠 sleep 偶遇竞争。

`audit_isolation.py` 在宿主创建真实随机 canary，并同时启动两个独立 attempt，验证私有目录、canary、管理数据库、凭据目录、Docker socket、另一个数据库、另一个宿主 ingress 和外网均不可访问；同时验证仅有 public 只读挂载。canary 内容和管理密码不写入结果。

relations-2 另有只报告的质量观测：一次页面请求从数据库向应用返回的行数，不应随未展示的子列表无限增长。质量反例保留相同页面和 SQL 往返但过量 materialize；其语义仍通过，质量必须未观测。其他任务尚不启用 LLM quality judge。

## 模型与结论门禁

仅 `muse-spark-1.3` 获准。不得调用 Claude、GPT 或任何其他模型，包括审查模型；必须先获得用户明确确认。provider 名称不代表模型身份；不能用其他模型冒用 Muse 名称。Muse 不可用时只继续离线工作，不代跑。

四条件为 A 无指导、B 固定相关全文、C 真实 semantic Top-3 全文、D 固定无关全文。query 在检索前冻结。semantic 不能自动降级 keyword；独立 embedding 模型的授权未解决前不调用。B/D 记录多种离线 tokenizer 的计数，未声称是 Muse 实际 token；正文长度不完全相等是残余混杂。

开发和确认各6题×4条件×3次，各72次。计划144次不包括连通性探针、校准、链路smoke或传输重试。初始预算、无工具输入和随机顺序见 private manifest；必须先补齐真实编码会话隔离、交付和精确模型身份验证，再执行对照，不能把应用容器校准当作模型工作区验证。

评分不合并隐藏总分：execution health、semantic、quality 独立。报告保留全部计划分母、失败与原始证据；用户必须能看到双方实际回答、代码与验收对比。离线 reference 比 starter 更正确只证明仪器判别力，不证明 Practice 带来模型收益。
