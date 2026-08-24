export type IssueLevel = "error" | "warning" | "suggestion";
export interface QualityIssue { id:string; ruleId:string; level:IssueLevel; title:string; matched:string; message:string; suggestion:string; start:number; end:number; }
export interface MarkedSegment { text:string; level?:IssueLevel; issueId?:string; }

interface Check { ruleId:string; level:IssueLevel; title:string; pattern:RegExp; message:string; suggestion:string; validate?:(match:RegExpExecArray)=>boolean; }
const checks:Check[]=[
  {ruleId:"R0001",level:"error",title:"非规范术语",pattern:/泥浆/g,message:"“泥浆”不是当前术语库首选名称。",suggestion:"建议替换为“钻井液”。"},
  {ruleId:"R0003",level:"warning",title:"产量术语不明确",pattern:/日产量/g,message:"日产量未说明具体介质。",suggestion:"明确为日产油量、日产气量、日产液量或日产水量。"},
  {ruleId:"R0004",level:"warning",title:"压力类型不明确",pattern:/(?<!井口|井底|地层|油管|套管|注入)压力(?!梯度|单位)/g,message:"压力未明确测点或类型。",suggestion:"补充井口、井底、地层、油管、套管或注入等限定。"},
  {ruleId:"R0005",level:"warning",title:"压力缺少单位",pattern:/(?:压力|压强)[：:=\s]*(-?\d+(?:\.\d+)?)(?![\d.]|\s*(?:MPa|kPa|Pa|bar))/gi,message:"压力数值缺少计量单位。",suggestion:"补充MPa、kPa等单位并声明表压或绝压。"},
  {ruleId:"R0009",level:"error",title:"孔隙度越界",pattern:/孔隙度[：:=\s]*(-?\d+(?:\.\d+)?)\s*%?/g,message:"孔隙度必须处于0%～100%。",suggestion:"检查小数/百分数表达、单位或原始测量值。",validate:m=>Number(m[1])<0||Number(m[1])>100},
  {ruleId:"R0010",level:"error",title:"饱和度越界",pattern:/(?:含油|含气|含水)?饱和度[：:=\s]*(-?\d+(?:\.\d+)?)\s*%?/g,message:"流体饱和度必须处于0%～100%。",suggestion:"核对数值、单位和样品深度。",validate:m=>Number(m[1])<0||Number(m[1])>100},
  {ruleId:"R0012",level:"error",title:"含水率越界",pattern:/含水率[：:=\s]*(-?\d+(?:\.\d+)?)\s*%?/g,message:"含水率必须处于0%～100%。",suggestion:"核对油水产量或百分数转换。",validate:m=>Number(m[1])<0||Number(m[1])>100},
  {ruleId:"R0013",level:"error",title:"井斜角越界",pattern:/井斜角[：:=\s]*(-?\d+(?:\.\d+)?)\s*°?/g,message:"井斜角超出0°～180°有效范围。",suggestion:"检查轨迹数据和角度单位。",validate:m=>Number(m[1])<0||Number(m[1])>180},
  {ruleId:"R0014",level:"error",title:"方位角越界",pattern:/方位角[：:=\s]*(-?\d+(?:\.\d+)?)\s*°?/g,message:"方位角应在0°～360°范围内。",suggestion:"检查方位基准和角度单位。",validate:m=>Number(m[1])<0||Number(m[1])>=360},
  {ruleId:"R0015",level:"error",title:"产量为负值",pattern:/(?:日产油量|日产气量|日产水量|日产液量|累计产量)[：:=\s]*(-\d+(?:\.\d+)?)/g,message:"生产量不能为负数。",suggestion:"检查冲销记录、符号、单位或数据版本。"},
  {ruleId:"R0002",level:"suggestion",title:"缩写建议补充全称",pattern:/\b(?:MD|TVD|ROP|WOB|ECD|GOR|WHP)\b/g,message:"专业缩写首次出现时宜同时给出全称。",suggestion:"在首次出现处补充中文或英文全称。"},
];

export function inspectText(text:string):QualityIssue[]{
  const issues:QualityIssue[]=[];
  for(const check of checks){check.pattern.lastIndex=0;let match:RegExpExecArray|null;while((match=check.pattern.exec(text))){if(check.validate&&!check.validate(match))continue;issues.push({id:`${check.ruleId}-${match.index}-${issues.length}`,ruleId:check.ruleId,level:check.level,title:check.title,matched:match[0],message:check.message,suggestion:check.suggestion,start:match.index,end:match.index+match[0].length});if(match[0].length===0)check.pattern.lastIndex++;}}
  return issues.sort((a,b)=>a.start-b.start||({error:0,warning:1,suggestion:2}[a.level]-{error:0,warning:1,suggestion:2}[b.level]));
}

export function markText(text:string,issues:QualityIssue[]):MarkedSegment[]{
  const segments:MarkedSegment[]=[];let cursor=0;
  for(const issue of issues){if(issue.start<cursor)continue;if(issue.start>cursor)segments.push({text:text.slice(cursor,issue.start)});segments.push({text:text.slice(issue.start,issue.end),level:issue.level,issueId:issue.id});cursor=issue.end;}
  if(cursor<text.length)segments.push({text:text.slice(cursor)});return segments;
}
