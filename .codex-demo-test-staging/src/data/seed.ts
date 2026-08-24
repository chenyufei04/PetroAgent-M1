export interface TermRecord {
  id: string; zh: string; en: string; abbr: string; domain: string; subdomain: string;
  definition: string; unit: string; aliases: string[]; source: string; status: "已审核" | "待审核";
}
export interface BaseRecord {
  id: string; type: "专业分类" | "计量单位" | "常用缩写" | "数据来源";
  name: string; code: string; description: string; parent: string; status: "启用" | "停用";
}
export interface RuleRecord {
  id: string; name: string; type: "术语规范" | "单位格式" | "数值范围" | "字段完整性" | "逻辑关系" | "时间顺序" | "编码命名";
  domain: string; severity: "错误" | "警告" | "建议"; condition: string; message: string;
  source: string; scope: string; status: "启用" | "停用"; template: boolean;
}

export const termRecords: TermRecord[] = [
  {id:"T0001",zh:"储层",en:"reservoir",abbr:"",domain:"油藏与地质",subdomain:"储层地质",definition:"具有储集并渗流油气能力的岩层。",unit:"",aliases:["储集层"],source:"GB/T 8423.1-2018",status:"已审核"},
  {id:"T0002",zh:"孔隙度",en:"porosity",abbr:"POR",domain:"油藏与地质",subdomain:"储层物性",definition:"岩石孔隙体积与岩石总体积之比。",unit:"%",aliases:["孔隙率"],source:"GB/T 8423.1-2018",status:"已审核"},
  {id:"T0003",zh:"渗透率",en:"permeability",abbr:"PERM",domain:"油藏与地质",subdomain:"储层物性",definition:"多孔介质允许流体通过能力的量度。",unit:"mD",aliases:[],source:"GB/T 8423.1-2018",status:"已审核"},
  {id:"T0004",zh:"含油饱和度",en:"oil saturation",abbr:"SO",domain:"油藏与地质",subdomain:"储层物性",definition:"孔隙中原油体积占有效孔隙体积的比例。",unit:"%",aliases:[],source:"GB/T 8423.1-2018",status:"已审核"},
  {id:"T0005",zh:"地层压力",en:"formation pressure",abbr:"FP",domain:"油藏与地质",subdomain:"油藏动态",definition:"地层孔隙流体所承受的压力。",unit:"MPa",aliases:["储层压力"],source:"GB/T 8423.1-2018",status:"已审核"},
  {id:"T0006",zh:"采收率",en:"recovery factor",abbr:"RF",domain:"油藏与地质",subdomain:"储量评价",definition:"累计采出量与地质储量之比。",unit:"%",aliases:[],source:"GB/T 8423.1-2018",status:"已审核"},
  {id:"T0007",zh:"测量深度",en:"measured depth",abbr:"MD",domain:"钻井工程",subdomain:"井眼轨迹",definition:"沿井眼轴线从测量基准面至测点的长度。",unit:"m",aliases:["斜深"],source:"WITSML",status:"已审核"},
  {id:"T0008",zh:"垂直深度",en:"true vertical depth",abbr:"TVD",domain:"钻井工程",subdomain:"井眼轨迹",definition:"测点与深度基准面之间的垂直距离。",unit:"m",aliases:["真垂深"],source:"WITSML",status:"已审核"},
  {id:"T0009",zh:"机械钻速",en:"rate of penetration",abbr:"ROP",domain:"钻井工程",subdomain:"钻井参数",definition:"单位时间内钻头钻进的井段长度。",unit:"m/h",aliases:["钻速"],source:"WITSML",status:"已审核"},
  {id:"T0010",zh:"钻压",en:"weight on bit",abbr:"WOB",domain:"钻井工程",subdomain:"钻井参数",definition:"钻进过程中施加在钻头上的轴向载荷。",unit:"kN",aliases:[],source:"WITSML",status:"已审核"},
  {id:"T0011",zh:"循环当量密度",en:"equivalent circulating density",abbr:"ECD",domain:"钻井工程",subdomain:"钻井液",definition:"循环状态下井底压力折算得到的钻井液等效密度。",unit:"g/cm³",aliases:[],source:"WITSML",status:"已审核"},
  {id:"T0012",zh:"井漏",en:"lost circulation",abbr:"",domain:"钻井工程",subdomain:"井下复杂",definition:"钻井液或其他工作液进入地层而发生损失的现象。",unit:"",aliases:["漏失"],source:"SY/T 行业标准",status:"已审核"},
  {id:"T0013",zh:"固井",en:"cementing",abbr:"",domain:"完井与固井",subdomain:"固井工程",definition:"向套管与井壁环空注入水泥浆并使其凝固的作业。",unit:"",aliases:[],source:"ISO/TC 67/SC 3",status:"已审核"},
  {id:"T0014",zh:"射孔",en:"perforating",abbr:"",domain:"完井与固井",subdomain:"完井工程",definition:"建立井筒与储层之间流动通道的作业。",unit:"",aliases:[],source:"GB/T 8423.1-2018",status:"已审核"},
  {id:"T0015",zh:"压裂",en:"hydraulic fracturing",abbr:"HF",domain:"完井与固井",subdomain:"储层改造",definition:"利用高压流体使地层形成裂缝并改善导流能力的作业。",unit:"",aliases:["水力压裂"],source:"GB/T 8423.1-2018",status:"已审核"},
  {id:"T0016",zh:"日产油量",en:"daily oil production",abbr:"",domain:"采油与生产",subdomain:"生产动态",definition:"油井或生产单元每日生产的原油体积或质量。",unit:"m³/d",aliases:["日油"],source:"PRODML",status:"已审核"},
  {id:"T0017",zh:"含水率",en:"water cut",abbr:"WC",domain:"采油与生产",subdomain:"生产动态",definition:"产出液中水所占的体积分数。",unit:"%",aliases:["综合含水"],source:"PRODML",status:"已审核"},
  {id:"T0018",zh:"气油比",en:"gas-oil ratio",abbr:"GOR",domain:"采油与生产",subdomain:"生产动态",definition:"规定条件下产气量与产油量之比。",unit:"m³/m³",aliases:[],source:"PRODML",status:"已审核"},
  {id:"T0019",zh:"井口压力",en:"wellhead pressure",abbr:"WHP",domain:"采油与生产",subdomain:"生产监测",definition:"在井口指定位置测得的流体压力。",unit:"MPa",aliases:[],source:"PRODML",status:"已审核"},
  {id:"T0020",zh:"注采比",en:"injection-production ratio",abbr:"IPR",domain:"注水与提高采收率",subdomain:"注水开发",definition:"一定时期内地下有效注入量与采出量之比。",unit:"",aliases:[],source:"GB/T 8423.1-2018",status:"待审核"},
  {id:"T0021",zh:"聚合物驱",en:"polymer flooding",abbr:"PF",domain:"注水与提高采收率",subdomain:"化学驱",definition:"向地层注入聚合物溶液以改善流度比的提高采收率方法。",unit:"",aliases:[],source:"ISO/TC 67/SC 10",status:"已审核"},
  {id:"T0022",zh:"油气分离器",en:"oil and gas separator",abbr:"",domain:"地面工程与集输",subdomain:"油气处理",definition:"用于分离油气混合物流中气相和液相的设备。",unit:"",aliases:["分离器"],source:"ISO/TC 67/SC 6",status:"已审核"},
  {id:"T0023",zh:"清管",en:"pigging",abbr:"",domain:"地面工程与集输",subdomain:"管道运输",definition:"使用清管器在管道内运行以完成清理或检测的作业。",unit:"",aliases:[],source:"ISO 5872:2025",status:"已审核"},
  {id:"T0024",zh:"自然伽马",en:"gamma ray",abbr:"GR",domain:"测井与试井",subdomain:"测井",definition:"测量地层天然放射性强度的测井方法或曲线。",unit:"API",aliases:["伽马"],source:"PWLS",status:"已审核"},
  {id:"T0025",zh:"表皮系数",en:"skin factor",abbr:"S",domain:"测井与试井",subdomain:"试井",definition:"表征井筒附近附加流动阻力的无量纲参数。",unit:"",aliases:["污染系数"],source:"GB/T 8423.1-2018",status:"已审核"},
];

export const baseRecords: BaseRecord[] = [
  {id:"D01",type:"专业分类",name:"油藏与地质",code:"RES",description:"储层、油藏、储量及开发地质相关术语",parent:"石油工程",status:"启用"},
  {id:"D02",type:"专业分类",name:"钻井工程",code:"DRL",description:"钻井装备、井眼轨迹、钻井液及井控",parent:"石油工程",status:"启用"},
  {id:"D03",type:"专业分类",name:"完井与固井",code:"COM",description:"固井、完井、射孔与储层改造",parent:"石油工程",status:"启用"},
  {id:"D04",type:"专业分类",name:"采油与生产",code:"PRO",description:"举升、生产动态与生产监测",parent:"石油工程",status:"启用"},
  {id:"D05",type:"专业分类",name:"注水与提高采收率",code:"EOR",description:"注水、化学驱、气驱及热采",parent:"石油工程",status:"启用"},
  {id:"D06",type:"专业分类",name:"地面工程与集输",code:"FAC",description:"油气处理、站场、管道和完整性",parent:"石油工程",status:"启用"},
  {id:"D07",type:"专业分类",name:"测井与试井",code:"LOG",description:"测井曲线、解释评价及压力测试",parent:"石油工程",status:"启用"},
  {id:"U01",type:"计量单位",name:"兆帕",code:"MPa",description:"压力单位，10⁶ Pa",parent:"压力",status:"启用"},
  {id:"U02",type:"计量单位",name:"米",code:"m",description:"长度及井深标准单位",parent:"长度",status:"启用"},
  {id:"U03",type:"计量单位",name:"毫达西",code:"mD",description:"储层渗透率常用单位",parent:"渗透率",status:"启用"},
  {id:"U04",type:"计量单位",name:"立方米每天",code:"m³/d",description:"液体体积流量常用单位",parent:"体积流量",status:"启用"},
  {id:"U05",type:"计量单位",name:"摄氏度",code:"℃",description:"温度常用单位",parent:"温度",status:"启用"},
  {id:"A01",type:"常用缩写",name:"测量深度",code:"MD",description:"Measured Depth",parent:"钻井工程",status:"启用"},
  {id:"A02",type:"常用缩写",name:"垂直深度",code:"TVD",description:"True Vertical Depth",parent:"钻井工程",status:"启用"},
  {id:"A03",type:"常用缩写",name:"机械钻速",code:"ROP",description:"Rate of Penetration",parent:"钻井工程",status:"启用"},
  {id:"A04",type:"常用缩写",name:"气油比",code:"GOR",description:"Gas-Oil Ratio",parent:"采油与生产",status:"启用"},
  {id:"S01",type:"数据来源",name:"国家标准",code:"GB/T",description:"全国标准信息公共服务平台发布的推荐性国家标准",parent:"国内标准",status:"启用"},
  {id:"S02",type:"数据来源",name:"石油天然气行业标准",code:"SY/T",description:"石油天然气行业推荐性标准",parent:"国内标准",status:"启用"},
  {id:"S03",type:"数据来源",name:"ISO/TC 67",code:"ISO",description:"油气工业及低碳能源国际标准",parent:"国际标准",status:"启用"},
  {id:"S04",type:"数据来源",name:"Energistics",code:"ENERGISTICS",description:"WITSML、PRODML、RESQML、UOM及PWLS",parent:"行业数据标准",status:"启用"},
  {id:"S05",type:"数据来源",name:"API",code:"API",description:"美国石油学会标准及MPMS术语",parent:"国际标准",status:"启用"},
];

export const ruleRecords: RuleRecord[] = [
  {id:"R0001",name:"术语必须使用规范名称",type:"术语规范",domain:"通用",severity:"警告",condition:"文本命中术语库中的旧称、禁用词或非首选同义词",message:"请使用术语库指定的规范名称。",source:"术语库映射",scope:"全部文档",status:"启用",template:false},
  {id:"R0002",name:"英文缩写首次出现需给出全称",type:"术语规范",domain:"通用",severity:"警告",condition:"英文缩写首次出现且上下文没有中文或英文全称",message:"首次使用缩写时应同时给出全称。",source:"文档编写规范",scope:"报告、设计、方案",status:"启用",template:false},
  {id:"R0003",name:"日产量术语必须明确介质",type:"术语规范",domain:"采油与生产",severity:"错误",condition:"仅出现“日产量”且未指明油、气、液或水",message:"请明确为日产油量、日产气量、日产液量或日产水量。",source:"PRODML数据对象",scope:"生产数据",status:"启用",template:false},
  {id:"R0004",name:"压力类型必须明确",type:"术语规范",domain:"通用",severity:"警告",condition:"仅记录“压力”，未说明井口、井底、油管、套管、地层或注入压力",message:"压力数据必须标明测点或压力类型。",source:"石油工程数据规范",scope:"监测与试验数据",status:"启用",template:false},
  {id:"R0005",name:"数值型工程参数必须带单位",type:"单位格式",domain:"通用",severity:"错误",condition:"压力、温度、深度、流量、密度或产量字段有数值但单位为空",message:"工程参数缺少计量单位。",source:"Energistics UOM",scope:"结构化数据",status:"启用",template:false},
  {id:"R0006",name:"井深统一使用米",type:"单位格式",domain:"钻井工程",severity:"警告",condition:"井深字段单位不是m且没有可验证的换算信息",message:"井深建议统一换算为米并保留原始单位。",source:"WITSML UOM",scope:"井与井筒数据",status:"启用",template:false},
  {id:"R0007",name:"压力需区分表压和绝压",type:"单位格式",domain:"通用",severity:"警告",condition:"关键压力字段未声明gauge或absolute基准",message:"请明确压力为表压还是绝压。",source:"计量规范",scope:"设计与试验数据",status:"启用",template:false},
  {id:"R0008",name:"同一序列单位必须一致",type:"单位格式",domain:"通用",severity:"错误",condition:"同一数据序列中出现多个单位且未执行换算",message:"同一序列存在混合单位，请统一单位后再计算。",source:"Energistics UOM",scope:"时间序列",status:"启用",template:false},
  {id:"R0009",name:"孔隙度取值范围",type:"数值范围",domain:"油藏与地质",severity:"错误",condition:"孔隙度<0%或孔隙度>100%",message:"孔隙度必须在0%～100%范围内。",source:"物理约束",scope:"储层物性",status:"启用",template:false},
  {id:"R0010",name:"流体饱和度取值范围",type:"数值范围",domain:"油藏与地质",severity:"错误",condition:"任一油、气、水饱和度<0%或>100%",message:"流体饱和度必须在0%～100%范围内。",source:"物理约束",scope:"储层物性",status:"启用",template:false},
  {id:"R0011",name:"饱和度总和一致性",type:"逻辑关系",domain:"油藏与地质",severity:"警告",condition:"So+Sg+Sw与100%的偏差超过配置容差",message:"油、气、水饱和度之和不满足一致性要求。",source:"物理约束",scope:"同深度同样品",status:"启用",template:true},
  {id:"R0012",name:"含水率取值范围",type:"数值范围",domain:"采油与生产",severity:"错误",condition:"含水率<0%或含水率>100%",message:"含水率必须在0%～100%范围内。",source:"物理约束",scope:"生产动态",status:"启用",template:false},
  {id:"R0013",name:"井斜角取值范围",type:"数值范围",domain:"钻井工程",severity:"错误",condition:"井斜角<0°或井斜角>180°",message:"井斜角超出有效范围。",source:"WITSML轨迹模型",scope:"井眼轨迹",status:"启用",template:false},
  {id:"R0014",name:"方位角取值范围",type:"数值范围",domain:"钻井工程",severity:"错误",condition:"方位角<0°或方位角≥360°",message:"方位角应在0°～360°范围内。",source:"WITSML轨迹模型",scope:"井眼轨迹",status:"启用",template:false},
  {id:"R0015",name:"产量不得为负值",type:"数值范围",domain:"采油与生产",severity:"错误",condition:"日产油、气、水、液量或累计产量<0",message:"生产量不能为负数；冲销数据应使用专门的数据标识。",source:"PRODML",scope:"生产数据",status:"启用",template:false},
  {id:"R0016",name:"生产记录关键字段完整",type:"字段完整性",domain:"采油与生产",severity:"错误",condition:"井号、统计时间、参数名称、数值或单位任一为空",message:"生产记录缺少必要字段。",source:"PRODML",scope:"生产数据",status:"启用",template:false},
  {id:"R0017",name:"测井曲线元数据完整",type:"字段完整性",domain:"测井与试井",severity:"错误",condition:"曲线名称、单位、起止深度或采样间隔为空",message:"测井曲线元数据不完整。",source:"WITSML/PWLS",scope:"测井曲线",status:"启用",template:false},
  {id:"R0018",name:"术语来源可追溯",type:"字段完整性",domain:"通用",severity:"警告",condition:"术语记录没有来源标准、标准版本或来源文件",message:"术语缺少可追溯的来源信息。",source:"术语治理要求",scope:"术语库",status:"启用",template:false},
  {id:"R0019",name:"累计产量单调性",type:"逻辑关系",domain:"采油与生产",severity:"错误",condition:"当前累计产量小于同一对象上一统计时刻累计产量",message:"累计产量发生倒退，请检查更正、单位或数据版本。",source:"生产数据逻辑",scope:"连续生产序列",status:"启用",template:false},
  {id:"R0020",name:"产液量组成一致性",type:"逻辑关系",domain:"采油与生产",severity:"警告",condition:"日产液量与日产油量+日产水量的偏差超过配置容差",message:"日产液量与油水分项合计不一致。",source:"生产数据逻辑",scope:"同井同日数据",status:"启用",template:true},
  {id:"R0021",name:"测量深度不小于垂直深度",type:"逻辑关系",domain:"钻井工程",severity:"错误",condition:"同一测点MD<TVD",message:"测量深度不应小于垂直深度。",source:"井眼轨迹几何约束",scope:"井眼轨迹",status:"启用",template:false},
  {id:"R0022",name:"井底流压与静压关系检查",type:"逻辑关系",domain:"测井与试井",severity:"警告",condition:"正常生产条件下井底流压高于同基准地层静压",message:"井底流压高于静压，请核对工况、时间和压力基准。",source:"渗流基本关系",scope:"正常生产井",status:"启用",template:true},
  {id:"R0023",name:"完井日期不得早于开钻日期",type:"时间顺序",domain:"钻井工程",severity:"错误",condition:"完井日期<开钻日期",message:"井生命周期日期顺序错误。",source:"井生命周期逻辑",scope:"井主数据",status:"启用",template:false},
  {id:"R0024",name:"投产日期不得早于完井日期",type:"时间顺序",domain:"采油与生产",severity:"错误",condition:"投产日期<完井日期",message:"投产日期不能早于完井日期。",source:"井生命周期逻辑",scope:"井主数据",status:"启用",template:false},
  {id:"R0025",name:"时间序列不得重复",type:"时间顺序",domain:"通用",severity:"警告",condition:"同一对象、参数和时间戳出现多条有效记录",message:"检测到重复时间点，请根据数据版本或优先级去重。",source:"数据质量规则",scope:"时间序列",status:"启用",template:false},
  {id:"R0026",name:"井号必须符合配置格式",type:"编码命名",domain:"通用",severity:"错误",condition:"井号不匹配当前油田配置的正则表达式",message:"井号格式不符合当前数据域的命名规则。",source:"企业主数据规范",scope:"井主数据",status:"启用",template:true},
  {id:"R0027",name:"数据对象标识必须唯一",type:"编码命名",domain:"通用",severity:"错误",condition:"同一数据域内对象ID重复",message:"数据对象标识重复。",source:"Energistics标识规范",scope:"全部结构化对象",status:"启用",template:false},
  {id:"R0028",name:"深度基准必须声明",type:"字段完整性",domain:"钻井工程",severity:"错误",condition:"MD、TVD或TVDSS存在但深度基准为空",message:"井深数据必须声明深度基准面。",source:"WITSML",scope:"井、井筒与测井",status:"启用",template:false},
];
