# PetroAgent M1

面向石油工程科研的第一阶段智能体内核。项目以 OPM 官方开放案例
`polymer_simple2D` 为主案例，以 `SPE9` 为跨场景验证案例，先建立一个
可测试、可追溯、可替换数据源的确定性分析底座，再在后续版本接入
LangGraph、RAG、OPM Flow 自动运行和 CMG。

> 当前版本：`0.1.0`  
> Python：`3.10+`  
> 当前边界：M1 确定性分析内核，不包含 LLM、RAG、Web 前端和自动运行模拟器。

## 1. 项目目标

M1 解决的不是“让大模型自由分析油藏”，而是先打通一条可审计链路：

```text
OPM Deck / OPM 导出 CSV
        ↓
数据源适配与统一字段
        ↓
确定性指标计算
        ↓
数据质量和物理规则校验
        ↓
科研曲线与 Markdown 报告
```

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

## 3. 目录结构

```text
petro-agent-m1/
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

## 4. 快速开始

### 4.1 Windows PowerShell

```powershell
cd F:\Projects\petro-agent-m1
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
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

## 9. 校验规则

当前实现的确定性规则包括：

| 规则 ID | 作用 |
|---|---|
| `DATA_NOT_EMPTY` | 数据集不能为空 |
| `TIME_MONOTONIC` | 时间必须单调不减 |
| `*_NONNEGATIVE` | 油率、水率、聚合物浓度不得为负 |
| `WATER_CUT_BOUNDS` | 含水率必须在 `[0, 1]` |
| `RECOVERY_BOUNDS` | 采收率必须在 `[0, 1]` |
| `RECOVERY_MONOTONIC` | 累计采收率不应下降 |
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

## 10. 如何扩展到其他石油工程方向

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

## 11. 测试

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

科研规则新增时，必须同步添加：

1. 正常样例；
2. 边界值；
3. 明确失败样例；
4. 单位或缺列异常样例。

## 12. 输出的可追溯性

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

## 13. 后续路线

### M1.1（当前）

- OPM 案例注册；
- 统一协议；
- CSV 分析；
- 规则校验；
- 图表和报告。

### M1.2

- 安装并自动调用 OPM Flow；
- 直接读取 summary / restart 输出；
- 建立水驱与聚合物驱成对运行配置；
- 增加运行清单和完整 provenance。

### M1.3

- 文献与官方文档 RAG；
- LangGraph 受控工作流；
- 工具选择、人工确认、失败重试；
- FastAPI 上传与任务接口。

### M2

- CMG STARS 适配器；
- 参数扫描和实验设计；
- 代理模型；
- 贝叶斯优化或进化算法；
- 最后才考虑强化学习与复杂多智能体。

## 14. 当前限制

- 仓库内的演示 CSV 不是 OPM 官方模拟输出；
- 尚未自动安装或运行 OPM Flow；
- 尚未直接解析 EGRID/UNRST/SMSPEC 等二进制结果；
- 累计产油量当前使用离散矩形积分，正式工作可替换为模拟器累计量；
- 未知 OOIP 时不会自动推导采收率；
- 未实现完整质量守恒；
- 未接入 LLM，不具备自然语言自主规划；
- 未接入数据库或前端。

这些限制是刻意的：第一阶段先保证计算工具、接口、规则和来源可验证，
再把智能体能力放在可靠内核外层。

## 15. 建议的首次正式实验

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

