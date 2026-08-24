import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir="outputs/quality-control-validation";await fs.mkdir(outputDir,{recursive:true});
const workbook=Workbook.create();const sheet=workbook.worksheets.add("实验数据");
const rows=[
  ["岩心-07","孔隙度",18,"%","常规岩心分析"],["井A-03","日产量",120,"m³/d","生产日报"],
  ["轨迹点-12","方位角",215,"°","定向井测量"],["井B-01","泥浆密度",1.2,"g/cm³","入井前检测"],
  ["岩心-02","含水饱和度",-5,"%","复测样品"],["井A-03","井口压力",12,"MPa","08:00测量"],
  ["井C-08","日产油量",-8,"m³/d","自动采集"],["轨迹点-08","井斜角",86,"°","定向井测量"],
  ["岩心-11","孔隙度",135,"%","实验室结果"],["井D-02","压力",12,"","试井记录"],
  ["井A-03","含水率",35,"%","生产日报"],["轨迹点-20","方位角",360,"°","定向井测量"],
  ["井E-06","MD",3200,"m","井深测量"],["井E-06","TVD",2950,"m","井深测量"],
  ["井F-09","含水率",105,"%","生产日报"],["轨迹点-21","井斜角",190,"°","定向井测量"],
  ["岩心-15","渗透率",32.5,"mD","常规岩心分析"],["井G-04","井底压力",18.5,"MPa","压力恢复测试"],
];
sheet.getRange("A1:E1").values=[["数据对象","检测项目","记录值","单位","数据说明"]];sheet.getRange(`A2:E${rows.length+1}`).values=rows;
sheet.getRange("A1:E1").format={fill:"#1677DC",font:{bold:true,color:"#FFFFFF"},borders:{preset:"outside",style:"thin",color:"#1267BE"}};
sheet.getRange(`A2:E${rows.length+1}`).format={borders:{insideHorizontal:{style:"thin",color:"#E7EBEF"}},verticalAlignment:"center",rowHeight:28};
sheet.getRange("A:A").format.columnWidth=18;sheet.getRange("B:B").format.columnWidth=22;sheet.getRange("C:C").format.columnWidth=14;sheet.getRange("D:D").format.columnWidth=14;sheet.getRange("E:E").format.columnWidth=28;
sheet.getRange(`C2:C${rows.length+1}`).format.numberFormat="0.00";sheet.freezePanes.freezeRows(1);sheet.showGridLines=false;
sheet.tables.add(`A1:E${rows.length+1}`,true,"PetroleumExperimentData").style="TableStyleMedium2";
const preview=await workbook.render({sheetName:"实验数据",range:`A1:E${rows.length+1}`,scale:1,format:"png"});await fs.writeFile(`${outputDir}/quality-control-validation-preview.png`,new Uint8Array(await preview.arrayBuffer()));
const check=await workbook.inspect({kind:"table",range:`实验数据!A1:E${rows.length+1}`,include:"values,formulas",tableMaxRows:25,tableMaxCols:8});console.log(check.ndjson);
const errors=await workbook.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:50},summary:"formula error scan"});console.log(errors.ndjson);
const output=await SpreadsheetFile.exportXlsx(workbook);await output.save(`${outputDir}/石油工程质控验证样本.xlsx`);
