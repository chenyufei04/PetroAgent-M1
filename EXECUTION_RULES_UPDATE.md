# 执行规则修订说明

## 本次目标

让 `python scripts/run_demo.py` 真正执行知识规则，并使新版与原始 M1 的运行行为
可以清晰区分、配置和审计。

## 主要修改

- 增加 `knowledge`、`legacy`、`hybrid` 三种规则执行模式；
- 演示案例默认使用 `knowledge`，执行 8 条 YAML 知识规则；
- `knowledge` 和 `hybrid` 模式下知识目录缺失时直接报错；
- `hybrid` 模式移除已经迁移到 YAML 的旧规则，避免重复校验；
- 目标概念无法映射时记录规则跳过原因，不再静默忽略；
- 在数据集元数据中记录规则加载、执行和跳过统计；
- `run_demo.py` 输出知识库版本、规则数量、通过/失败数量和报告路径；
- README 增加执行模式和配置说明；
- 增加知识模式、旧模式、无效模式及规则跳过行为测试。

## 默认配置

```yaml
knowledge:
  enabled: true
  execution_mode: knowledge
  context:
    representation: decimal_fraction
```

## 默认演示结果

```text
完成: polymer_simple2d_demo
规则执行模式: knowledge
知识库版本: Knowledge Foundation v0.1
知识规则: 加载 8 条, 执行 8 条, 跳过 0 条
校验结果: 通过 8 条, 未通过 0 条
```

## 验证结果

```text
10 passed
知识基础层校验通过 / Knowledge foundation validation passed
```

演示数据仍是用于验证管线的合成数据，以上结果证明执行链和规则机制可用，不代表
真实油田或论文实验结论。
