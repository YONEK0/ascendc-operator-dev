# 算子设计范式索引

> 本索引只负责导航。检索规则以 [`references/index.md`](references/index.md) 为准：
> 先应用 Skill 入口的组合范式规则；未命中时从 `paradigms/routes.yaml` 查 `op.paradigms`，不要扫描目录推断。

## 先读

- [范式知识索引](references/index.md)：检索规则、按问题选择、平台与语言范围。
- [范式资料维护](references/paradigms/README.md)：目录组织、注册与校验。
- [通用方法（Ascend C）](references/paradigms/general-methodology.md)。
- [通用方法（DSL）](references/paradigms/general-methodology-dsl.md)。
- [开源算子表](references/reference-ops/open_source_operator_table.md)：筛选可检查的现有实现。

## 按范式

| 范式 | 入口 | 典型问题 |
|---|---|---|
| Broadcast | [patterns.md](references/paradigms/broadcast/patterns.md) | 形状归一化、广播轴、切分 |
| Reduction | [patterns.md](references/paradigms/reduction/patterns.md) | 归约轴、缓存树、资源规划 |
| Contraction | [patterns.md](references/paradigms/contraction/patterns.md) | 指标映射、选块、任务调度、分层缓冲 |
| FA 组合 | [patterns.md](references/paradigms/fused_composite/fa/patterns.md) | Contraction + Reduction + Broadcast 组合 |
| 公共规则 | [common/](references/paradigms/common/) | 广播规则、Cast、DataCopyPad、NDDMA、同步一致性、值依赖处理、VF 编程 |

## 按知识类型

| 知识类型 | 入口 |
|---|---|
| API 约束与签名 | [knowledge/api/index.md](references/knowledge/api/index.md) |
| Kernel / VF / Reg-MicroAPI 组织 | [knowledge/patterns/index.md](references/knowledge/patterns/index.md) |
| 精度、数值稳定性、错误定位 | [knowledge/pitfalls/index.md](references/knowledge/pitfalls/index.md) |
| 构建、验证、上下文恢复 | [knowledge/dev-experience/index.md](references/knowledge/dev-experience/index.md) |
| RegBase 开发方法 | [regbase_development_guide.md](references/knowledge/regbase_development_guide.md) |

## 平台与语言范围

- `ascend950 / regbase`：读 `knowledge/` 下的 API、模式、经验与 pitfalls。
- `ascend910b / membase`：只在明确兼容性问题中参考，核对适用平台。
- `dsl / CANNBotDSL`：从范式入口选择 DSL 适配层；`knowledge/` 与 `reference-ops/` 不作为 DSL 默认参考。

算子表只用于筛选可检查的实现；能否复用必须结合具体代码、规格和平台约束判断。
