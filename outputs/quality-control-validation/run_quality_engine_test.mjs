import { inspectText } from "../../.codex-demo-test-staging/src/services/qualityEngine.ts";

const cases=[
  ["CASE-001","井口压力：12 MPa；孔隙度：18%；含水率：35%。",[]],
  ["CASE-002","本井段泥浆密度为1.20 g/cm³。",["R0001"]],
  ["CASE-003","该井日产量：120 m³/d。",["R0003"]],
  ["CASE-004","实验记录压力：12。",["R0004","R0005"]],
  ["CASE-005","岩心样品孔隙度：135%。",["R0009"]],
  ["CASE-006","该层含水饱和度：-5%。",["R0010"]],
  ["CASE-007","当前生产含水率：105%。",["R0012"]],
  ["CASE-008","轨迹测点井斜角：190°。",["R0013"]],
  ["CASE-009","轨迹测点方位角：360°。",["R0014"]],
  ["CASE-010","该井日产油量：-8 m³/d。",["R0015"]],
  ["CASE-011","测点MD：3200 m，TVD：2950 m。",["R0002","R0002"]],
  ["CASE-012","测量深度为3200 m，垂直深度为2950 m。",[]],
  ["CASE-013","泥浆性能异常，孔隙度：120%，日产量：80 m³/d。",["R0001","R0009","R0003"]],
  ["CASE-014","井底压力：18.5 MPa；井斜角：86°；方位角：215°。",[]],
];
let passed=0;
for(const [id,text,expected] of cases){const actual=inspectText(text).map(x=>x.ruleId).sort();const target=[...expected].sort();const ok=JSON.stringify(actual)===JSON.stringify(target);if(ok)passed++;console.log(JSON.stringify({id,ok,expected:target,actual}));}
console.log(JSON.stringify({summary:{passed,total:cases.length,accuracy:`${(passed/cases.length*100).toFixed(1)}%`}}));
if(passed!==cases.length)process.exitCode=1;
