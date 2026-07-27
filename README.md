# PetroAgent M1

面向石油工程科研的第一阶段智能体内核。项目以 OPM 官方开放案例
`polymer_simple2D` 为主案例，以 `SPE9` 为跨场景验证案例，先建立一个
可测试、可追溯、可替换数据源的确定性分析底座，并在同一项目中建设
`PetroleumEngineeringCoreOntology v0.1`（石油工程核心本体 v0.1）。
后续再接入 Neo4j、LangGraph、RAG、OPM Flow 自动运行和 CMG。

> 当前版本：`0.2.0-dev / Knowledge Foundation v0.1`  
> Python：`3.10+`  
> 当前边界：确定性分析内核＋YAML知识基础层；不包含 LLM、RAG、Neo4j、
> Web 前端和自动运行模拟器。

## 1. 项目目标

M1 解决的不是“让大模型自由分析油藏”，而是先打通一条可审计链路：

```text
OPM Deck / OPM 导出 CSV
        ↓
数据源适配与统一字段
        ↓
参数、单位和概念对齐
        ↓
确定性指标计算
        ↓
知识规则检索＋确定性规则执行
        ↓
带来源的科研曲线与 Markdown 报告
```

项目遵循两条边界：

1. **确定性分析内核负责计算**：数据读取、指标计算、数值判断、绘图和报告；
2. **知识基础层负责语义与证据**：实体、关系、参数、单位、规则、适用条件和来源。

知识图谱不会代替数值模拟和确定性计算，大模型也不会被当作数值证据。

第一版正式数据来源为：

| 案例 | 上游仓库 | 本项目用途 |
|---|---|---|
| `polymer_simple2D` | `OPM/opm-tests` | 聚合物驱主案例，验证化学驱领域包 |
| `SPE9` | `OPM/opm-data` | 黑油/水驱跨案例，验证核心层不依赖聚合物 |

上游数据不会伪装成项目自有数据。下载脚本会记录仓库、提交哈希和子目录。
请同时遵守上游仓库的许可证和通知。

## 2. 已完成能力

- 统一科研数据对象 `CanonicalDataset`；
- 标准 CSV 字段映射和必需字段检查；
- Eclipse/OPM Deck 的 `INCLUDE` 依赖扫描与关键词概览；
- 公共油藏指标计算：含水率、累计产油量、注入 PV（元数据足够时）；
- 聚合物驱领域包：聚合物阶段识别和浓度非负检查；
- 通用规则：时间顺序、非负流量、含水率边界、采收率边界与单调性；
- 自动生成油率、含水率、采收率、注入井 BHP、聚合物浓度曲线；
- 自动生成带来源、规则状态和解释限制的 Markdown 报告；
- CLI 命令、演示数据、单元测试和端到端测试；
- OPM 两个官方案例的稀疏下载脚本。
- 石油工程上层实体、通用关系、参数和单位的 YAML 定义；
- 全部实体与关系的中文、英文对照名称；
- `YamlKnowledgeService` 概念解析、数据集对齐、规则检索和来源追溯；
- YAML 驱动的通用规则执行器；
- 聚合物驱首个领域子图谱；
- 报告中的观测值、期望值、来源和适用条件。

## 3. 目录结构

```text
petro-agent-m1/
├── knowledge_graph/                  # 可审查、可版本管理的知识源
│   ├── core/                         # 上层实体、关系、参数、单位、规则
│   ├── domains/chemical_eor/         # 首个聚合物驱验证子图谱
│   ├── mappings/                     # 标准字段、OPM、未来CMG映射
│   ├── provenance/                   # 来源与证据
│   └── standards/                    # 标准目录骨架
├── config/cases/                    # 每个案例的字段、单位和领域包配置
│   ├── polymer_simple2d.yaml
│   └── spe9.yaml
├── data/
│   ├── raw/                         # OPM 原始案例，默认不提交 Git
│   ├── processed/                   # 标准化结果，默认不提交 Git
│   └── demo/                        # 仅用于管线测试的明确标注演示数据
├── outputs/
│   ├── figures/
│   ├── reports/
│   └── runs/
├── scripts/
│   ├── fetch_opm_data.py            # 下载官方案例并记录上游修订号
│   └── run_demo.py
├── src/petro_agent/
│   ├── adapters/                    # CSV、Deck、未来 OPM/CMG/实验数据适配器
│   ├── core/                        # 与石油工程具体方向无关的协议和管线
│   ├── knowledge/                   # 知识模型、服务接口、YAML实现、规则执行
│   ├── domain_packs/
│   │   ├── common_reservoir/        # 公共油藏规则与计算
│   │   └── polymer_flooding/        # 聚合物驱专用逻辑
│   ├── reporting/                   # 图表与报告
│   ├── validators/                  # 确定性校验
│   ├── cli.py
│   └── pipeline.py
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

`knowledge_graph/` 和 `src/petro_agent/knowledge/` 必须分开：

- `knowledge_graph/` 保存研究人员可直接审查的知识内容；
- `src/petro_agent/knowledge/` 保存加载、检索、匹配和执行知识的程序；
- 将来 Neo4j 只是查询载体，Git 中的 YAML 仍是可追溯的知识源。

## 4. 快速开始

### 4.1 Windows PowerShell

```powershell
cd F:\Projects\petro-agent-m1
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
python scripts\validate_knowledge.py
python scripts\run_demo.py
```

如需使用清华镜像：

```powershell
python -m pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4.2 macOS / Linux

```bash
cd petro-agent-m1
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
python scripts/validate_knowledge.py
python scripts/run_demo.py
```

成功后会生成：

```text
outputs/reports/polymer_simple2d_demo.md
outputs/runs/polymer_simple2d_demo_canonical.csv
outputs/figures/polymer_simple2d_demo_*.png
```

演示 CSV 是为了离线验证代码而人工构造的平滑数据，配置中明确标为
`generated_demo_not_official_opm_output`。它不能作为论文实验结果，
正式分析必须替换成 OPM Flow 实际输出。

## 5. 获取 OPM 官方案例

机器需安装 Git，并能够访问 GitHub。

```bash
python scripts/fetch_opm_data.py polymer_simple2D spe9
```

结果默认写入：

```text
data/raw/polymer_simple2D/
data/raw/spe9/
```

每个目录会附加 `UPSTREAM_REVISION.txt`，记录：

- 上游仓库；
- Git 提交哈希；
- 提取的子目录。

脚本在目标目录已存在时会停止，避免静默覆盖研究数据。

也可分别下载：

```bash
python scripts/fetch_opm_data.py polymer_simple2D
python scripts/fetch_opm_data.py spe9
```

## 6. 检查 OPM/Eclipse Deck

找到案例主 `.DATA` 文件后运行：

```bash
petro-agent inspect-deck --input data/raw/polymer_simple2D/CASE.DATA
```

将 `CASE.DATA` 替换成该目录中实际主文件名。命令输出：

- 根文件绝对路径；
- 递归访问的 INCLUDE 文件；
- 发现的关键词；
- 缺失的 INCLUDE 文件。

这一步只检查输入组织和依赖完整性，不运行数值模拟，也不证明模型物理正确。

## 7. 接入 OPM Flow 实际结果

当前 M1 不绑定某个 OPM 版本或二进制输出解析库。推荐先用你安装的
OPM Flow 运行案例，再将 summary/well 结果导出为 CSV，映射到以下标准字段。

| 标准字段 | 单位 | 必需 | 常见来源含义 |
|---|---:|---:|---|
| `time_days` | day | 是 | 模拟时间 |
| `injected_pv` | PV | 否 | 累计注入孔隙体积 |
| `oil_rate_m3_day` | m³/day | 聚合物演示必需 | 总/选定生产井油率 |
| `water_rate_m3_day` | m³/day | 聚合物演示必需 | 总/选定生产井水率 |
| `water_cut_fraction` | fraction | 否 | 可由油水流量计算 |
| `cumulative_oil_m3` | m³ | 否 | 可由油率和时间近似积分 |
| `recovery_factor_fraction` | fraction | 否 | 累计产油量 / OOIP |
| `injector_bhp_bar` | bar | 否 | 注入井井底压力 |
| `polymer_concentration_kg_m3` | kg/m³ | 否 | 注入或生产聚合物浓度 |
| `cumulative_injected_water_m3` | m³ | 否 | 配合孔隙体积计算注入 PV |

如果导出列名不同，在 YAML 中配置映射，不要修改核心代码：

```yaml
column_mapping:
  TIME: time_days
  FOPR: oil_rate_m3_day
  FWPR: water_rate_m3_day
  FWCT: water_cut_fraction
```

注意：OPM summary 关键字可能是现场总量或单井量，单位也受 deck 单位制和
导出工具影响。上面的映射只是结构示例，必须先核实实际结果的对象、符号和单位。

准备好 CSV 后运行：

```bash
petro-agent analyze \
  --input data/processed/polymer_simple2d_result.csv \
  --config config/cases/polymer_simple2d.yaml \
  --output outputs
```

SPE9 使用：

```bash
petro-agent analyze \
  --input data/processed/spe9_result.csv \
  --config config/cases/spe9.yaml \
  --output outputs
```

## 8. 统一数据协议

所有数据源最终都转换成 `CanonicalDataset`：

```python
CanonicalDataset(
    case_id="polymer_simple2d",
    domain="reservoir_engineering",
    process="polymer_flooding",
    frame=dataframe,
    units={"time_days": "day"},
    source=SourceInfo(
        source_type="opm_flow_export",
        model="polymer_simple2D",
        source_files=["result.csv"],
        repository="https://github.com/OPM/opm-tests",
        revision="<commit sha>",
    ),
    metadata={},
)
```

核心分析只依赖标准字段，不依赖 `FOPR`、`FWCT`、`WBHP` 或 CMG 的原始字段。
以后接入 CMG、实验 Excel、Volve、钻井数据时，应新增适配器或领域包，而不是
在核心工作流中堆叠条件判断。

## 9. 知识基础层 v0.1

### 9.1 中英文实体约定

所有正式实体至少包含稳定 ID、中文名和英文名：

```yaml
- concept_id: reservoir
  concept_type: asset
  name_zh: 油气藏
  name_en: Reservoir
  aliases_zh:
    - 储层
```

`concept_id` 是程序、数据映射和未来 Neo4j 使用的稳定标识，不随显示语言改变。
中文和英文名称用于科研阅读、检索、报告与图形化展示。别名必须按语言分开存储，
避免把中文、英文缩写和源系统字段混在一个不可审查的列表里。

首版上层实体包括：

| 稳定 ID | 中文名 | 英文名 |
|---|---|---|
| `domain` | 工程领域 | Engineering Domain |
| `asset` | 工程资产 | Engineering Asset |
| `formation` | 地层 | Formation |
| `reservoir` | 油气藏 | Reservoir |
| `well` | 井 | Well |
| `wellbore` | 井筒 | Wellbore |
| `material` | 工程材料 | Engineering Material |
| `fluid` | 流体 | Fluid |
| `equipment` | 设备 | Equipment |
| `operation` | 工程作业 | Engineering Operation |
| `method` | 工程方法 | Engineering Method |
| `parameter` | 工程参数 | Engineering Parameter |
| `unit` | 计量单位 | Measurement Unit |
| `dataset` | 数据集 | Dataset |
| `model` | 工程模型 | Engineering Model |
| `software` | 软件工具 | Software Tool |
| `standard` | 标准 | Standard |
| `standard_clause` | 标准条款 | Standard Clause |
| `rule` | 工程规则 | Engineering Rule |
| `evidence` | 证据 | Evidence |
| `organization` | 组织机构 | Organization |
| `research_task` | 科研任务 | Research Task |

### 9.2 中英文关系约定

关系同样不得只写英文：

```yaml
- relation_id: HAS_PARAMETER
  name_zh: 具有参数
  name_en: Has Parameter
```

存在明确反向语义时，可同时声明中英文反向名称。例如：

```yaml
- relation_id: PART_OF
  name_zh: 是其组成部分
  name_en: Part Of
  inverse_name_zh: 包含组成部分
  inverse_name_en: Has Part
```

首版关系包括 `IS_A / 是一种`、`属于工程领域 / Belongs To Domain`、
`作用于 / Acts On`、`使用材料 / Uses Material`、`具有参数 / Has Parameter`、
`使用单位 / Uses Unit`、`约束 / Constrains`、`来源于 / Derived From`、
`由其支持 / Supported By`、`适用于 / Applies To` 和
`映射自 / Mapped From` 等。完整定义见
`knowledge_graph/core/relations.yaml`。

### 9.3 参数与标准字段映射

案例 YAML 负责说明实际数据如何进入管线；核心知识文件负责说明字段的工程含义：

```text
原始字段 FOPR
    → 案例/OPM映射 oil_rate_m3_day
    → 图谱概念 oil_production_rate
    → 中文名 产油速率 / 英文名 Oil Production Rate
    → 标准单位 m3/day
```

这种分层保证 OPM、CMG、实验 Excel 和其他数据源可以共用同一概念。CMG 映射
当前保留为空模板；在确认具体模拟器模块、导出格式和单位制前不做猜测映射。

### 9.4 知识服务接口

当前实现为 `YamlKnowledgeService`，提供：

```python
resolve_concept(term)
resolve_dataset(dataset)
find_rules(concept_id, context)
trace_evidence(rule_id)
```

未来的 `Neo4jKnowledgeService` 必须遵循同一接口。分析管线不应知道规则来自
YAML、Neo4j、标准目录还是其他知识载体。

### 9.5 当前联合执行链路

```text
CSV Adapter
→ CanonicalDataset
→ 领域包确定性指标计算
→ 字段与中英双语概念对齐
→ 按 domain/process/representation 检索适用规则
→ RuleEngine 确定性执行
→ 带来源和适用条件的 ValidationFinding
→ Markdown 报告
```

案例可通过以下配置启用知识层：

```yaml
knowledge:
  enabled: true
  context:
    representation: decimal_fraction
```

如需隔离排查旧管线，可临时设置 `enabled: false`；正式研究运行建议保持开启。

## 10. 校验规则

当前实现的确定性规则包括：

| 规则 ID | 作用 |
|---|---|
| `CORE-DATA-001` | 数据集不能为空 / Dataset Must Not Be Empty |
| `CORE-TIME-001` | 模拟时间单调不减 / Simulation Time Monotonic |
| `CORE-PROD-001/002` | 油率、水率非负 / Non-negative Production Rates |
| `CORE-PROD-003` | 含水率位于 `[0, 1]` / Valid Water Cut Range |
| `CORE-RECOVERY-001` | 采收率位于 `[0, 1]` / Valid Recovery Factor Range |
| `CORE-RECOVERY-002` | 采收率单调不减 / Monotonic Recovery Factor |
| `EOR-POLYMER-001` | 聚合物浓度非负 / Non-negative Polymer Concentration |
| `POLYMER_COLUMN_PRESENT` | 提醒聚合物案例是否存在浓度字段 |

规则分为 `error` 和 `warning`。当前报告会完整记录所有规则；CLI 不会仅凭一条
warning 判定整个科研结论失败。

下一步应增加：

- 网格饱和度边界；
- `So + Sw (+ Sg) ≈ 1`；
- 聚合物质量守恒误差；
- 注入端到生产端压力合理性；
- 井控约束是否生效；
- 水驱/聚合物驱的同条件配对检查；
- 相渗、PVT 和单位一致性检查。

基础规则已从 Python 硬编码迁移至 `knowledge_graph/core/rules.yaml`。
无法安全声明为简单比较运算的复杂领域校验仍可留在 Python 中，但必须返回唯一
规则 ID，避免与 YAML 规则重复。

来源类型分为项目内部数据质量定义、基础数学/物理约束、正式标准、论文或其他
证据。当前 `petroleum_engineering_core` 只表示不依赖特定标准版本的基础约束，
**不冒充行业标准或标准条款**。

## 11. 如何扩展到其他石油工程方向

### 新增数据源

实现 `DatasetAdapter` 协议：

```python
class DatasetAdapter(Protocol):
    def load(self, source: Path, config: dict) -> CanonicalDataset:
        ...
```

适合新增：

- `OpmSummaryAdapter`
- `CmgResultAdapter`
- `ExperimentalExcelAdapter`
- `VolveProductionAdapter`

### 新增领域包

实现 `DomainPack` 的 `enrich` 和 `validate`：

```python
class DrillingPack:
    name = "drilling"

    def enrich(self, dataset):
        return dataset

    def validate(self, dataset):
        return []
```

然后在 `pipeline.py` 注册，并在案例 YAML 中声明：

```yaml
domain_packs:
  - drilling
```

可以按同一方式加入：

- 水驱；
- 气驱和 CO₂-EOR；
- CO₂ 地质封存；
- 生产工程；
- 钻井工程；
- 完井工程；
- 井网优化。

### 新增实体、关系或规则

1. 为对象选择稳定、语言无关的 `concept_id` 或 `relation_id`；
2. 同时填写 `name_zh` 与 `name_en`；
3. 参数需声明标准单位，并加入 `canonical_fields.yaml` 映射；
4. 规则必须声明唯一 ID、类型、目标概念、运算符、级别和来源；
5. 有适用前提时，同时写入 `conditions` 和中英文适用范围；
6. 运行 `python scripts/validate_knowledge.py` 和 `pytest -q`；
7. 正式标准必须在 `standards/catalog.yaml` 中记录版本与发布机构。

第一版规则引擎支持：

- `not_empty`
- `between`
- `greater_than_or_equal`
- `monotonic_non_decreasing`

复杂公式不要用字符串 `eval` 写进 YAML，应保留为经过测试的 Python 执行器。

## 12. 测试

运行全部测试：

```bash
pytest -q
```

当前覆盖：

- 含水率和累计油计算；
- 含水率越界识别；
- 采收率单调性；
- Deck INCLUDE 递归扫描；
- 从 CSV 到图表、标准化结果和报告的端到端链路。
- 中文、英文概念名称解析；
- YAML规则检索、执行和来源回溯。

科研规则新增时，必须同步添加：

1. 正常样例；
2. 边界值；
3. 明确失败样例；
4. 单位或缺列异常样例。

## 13. 输出的可追溯性

当前报告会记录数据来源类型、模型、仓库、行数、摘要、规则结果和图表。
正式研究运行还应额外保存：

- 原始 deck 与哈希；
- OPM Flow 版本和启动命令；
- 操作系统与依赖锁定文件；
- 输出提取脚本及参数；
- 上游仓库 commit；
- 字段映射与单位确认人；
- 对照实验参数差异；
- 每次运行的唯一 `run_id`。

项目不会把“LLM 的合理解释”当成数值校验。未来接入 LLM 后，报告应明确区分：

- 数据直接事实；
- 确定性公式结果；
- 校验规则结论；
- 文献支持解释；
- LLM 推断与待验证假设。

## 14. 后续路线

### M1.1（已完成）

- OPM 案例注册；
- 统一协议；
- CSV 分析；
- 规则校验；
- 图表和报告。

### M1.2（当前：知识基础层 v0.1）

- 石油工程上层实体与中英双语关系；
- 参数、单位、来源和规则格式；
- YAML知识服务与规则执行器；
- 标准字段概念映射；
- 聚合物驱首个验证子图谱；
- 报告证据追溯。

### M1.3

- 安装并自动调用 OPM Flow；
- 直接读取 summary / restart 输出；
- 建立水驱与聚合物驱成对运行配置；
- 增加运行清单和完整 provenance。

### M1.4

- 扩充标准目录、条款和版本关系；
- 增加知识结构 Schema 校验；
- 增加 OPM 结果字段与单位的版本化映射；
- 达到一定规模后导入 Neo4j，并保持 YAML 为知识源。

### M2

- 文献与官方文档 RAG；
- LangGraph 受控工作流；
- 工具选择、人工确认、失败重试；
- FastAPI 上传与任务接口。

### M3

- CMG STARS 适配器；
- 参数扫描和实验设计；
- 代理模型；
- 贝叶斯优化或进化算法；
- 最后才考虑强化学习与复杂多智能体。

## 15. 当前限制

- 仓库内的演示 CSV 不是 OPM 官方模拟输出；
- 尚未自动安装或运行 OPM Flow；
- 尚未直接解析 EGRID/UNRST/SMSPEC 等二进制结果；
- 累计产油量当前使用离散矩形积分，正式工作可替换为模拟器累计量；
- 未知 OOIP 时不会自动推导采收率；
- 未实现完整质量守恒；
- 未接入 LLM，不具备自然语言自主规划；
- 知识实体、关系和规则仍是 v0.1 小规模骨架；
- 尚未导入正式标准全文、条款或论文证据；
- 未接入 Neo4j，当前不提供多跳图查询和图形化浏览；
- CMG 字段映射尚未在具体导出结果上验证；
- 未接入数据库或前端。

这些限制是刻意的：第一阶段先保证计算工具、接口、规则和来源可验证，
再把智能体能力放在可靠内核外层。

## 16. 建议的首次正式实验

1. 下载 `polymer_simple2D` 和 `SPE9`；
2. 检查两个案例的主 Deck 和 INCLUDE 完整性；
3. 在固定 OPM Flow 版本下分别运行；
4. 保留原始输出和运行命令；
5. 编写一个版本固定的结果导出适配器；
6. 将 `polymer_simple2D` 拆成水驱基线与聚合物方案；
7. 用相同终止时间或注入 PV 对齐；
8. 比较油率、含水率、累计油、采收率和注入井 BHP；
9. 增加饱和度与聚合物质量守恒规则；
10. 生成第一份可重复的正式分析报告。

完成这十步后，再接入 LangGraph。这样 Agent 调用的是已经验证的科研工具，
而不是临时生成未经检验的计算代码。
