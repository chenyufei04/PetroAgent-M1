<script setup lang="ts">
import { computed, ref } from "vue";
import { inspectText, markText, type IssueLevel, type QualityIssue } from "../services/qualityEngine";

interface QualityFile { id:string; file:File; text:string; status:"waiting"|"parsing"|"ready"|"error"; saveStatus:"saving"|"saved"|"save-error"; savedPath?:string; error?:string; }
const accepted=".xlsx,.xls,.csv,.tsv,.doc,.docx,.txt,.md,.json,.xml";
const files=ref<QualityFile[]>([]);const activeId=ref("");const picker=ref<HTMLInputElement>();const dragging=ref(false);const selectedIssue=ref("");
const activeFile=computed(()=>files.value.find(x=>x.id===activeId.value));
const issues=computed(()=>activeFile.value?.status==="ready"?inspectText(activeFile.value.text):[]);
const segments=computed(()=>activeFile.value?markText(activeFile.value.text,issues.value):[]);
const counts=computed(()=>({error:issues.value.filter(x=>x.level==="error").length,warning:issues.value.filter(x=>x.level==="warning").length,suggestion:issues.value.filter(x=>x.level==="suggestion").length}));
const levelLabel:Record<IssueLevel,string>={error:"错误",warning:"警告",suggestion:"建议"};

async function parseFile(file:File):Promise<string>{
  const extension=file.name.split(".").pop()?.toLowerCase();
  if(extension==="xlsx")throw new Error("Excel文件需要由本地Python服务解析。");
  if(extension==="xls")throw new Error("旧版XLS暂不支持浏览器安全解析，请另存为XLSX后上传。");
  if(extension==="docx"){const {default:mammoth}=await import("mammoth");const result=await mammoth.extractRawText({arrayBuffer:await file.arrayBuffer()});return result.value;}
  if(extension==="doc")throw new Error("旧版DOC暂不支持浏览器解析，请另存为DOCX后上传。");
  return await file.text();
}
async function saveUploadedFile(item:QualityFile):Promise<string|undefined>{
  const formData=new FormData();formData.append("file",item.file);
  try{const response=await fetch("/api/quality/upload",{method:"POST",body:formData});const result=await response.json() as {path?:string;extracted_text?:string;detail?:string};if(!response.ok)throw new Error(result.detail??`保存失败（${response.status}）`);item.savedPath=result.path;item.saveStatus="saved";return result.extracted_text;}
  catch(error){item.saveStatus="save-error";item.error=`文件未保存到uploads：${(error as Error).message}`;return undefined;}
}
async function addFiles(input:FileList|File[]){
  const incoming=Array.from(input);const existing=new Set(files.value.map(x=>`${x.file.name}-${x.file.size}-${x.file.lastModified}`));
  const added:QualityFile[]=incoming.filter(file=>!existing.has(`${file.name}-${file.size}-${file.lastModified}`)).map(file=>({id:crypto.randomUUID(),file,text:"",status:"waiting",saveStatus:"saving"}));files.value.push(...added);
  if(!activeId.value&&added[0])activeId.value=added[0].id;
  for(const addedItem of added){const item=files.value.find(current=>current.id===addedItem.id)!;item.status="parsing";try{const serverText=await saveUploadedFile(item);const extension=item.file.name.split(".").pop()?.toLowerCase();if(extension==="xlsx"&&!serverText)throw new Error(item.error??"Excel解析服务不可用，请确认后端已启动。");item.text=serverText??await parseFile(item.file);item.status="ready";}catch(error){item.status="error";item.error=(error as Error).message;}}
  if(picker.value)picker.value.value="";
}
function onDrop(event:DragEvent){event.preventDefault();dragging.value=false;if(event.dataTransfer)addFiles(event.dataTransfer.files);}
function removeFile(id:string){files.value=files.value.filter(x=>x.id!==id);if(activeId.value===id)activeId.value=files.value[0]?.id??"";}
function selectIssue(issue:QualityIssue){selectedIssue.value=issue.id;document.querySelector(`[data-issue="${issue.id}"]`)?.scrollIntoView({behavior:"smooth",block:"center"});}
</script>

<template>
  <section class="quality-page">
    <aside class="quality-left">
      <div class="quality-title"><h1>数据质控</h1><p>上传实验或工程数据进行校验</p></div>
      <div class="quality-upload" :class="{dragging}" @dragenter="dragging=true" @dragleave="dragging=false" @dragover.prevent @drop="onDrop" @click="picker?.click()">
        <div>＋</div><strong>选择或拖拽文件</strong><span>Excel、CSV、Word、TXT、JSON、XML</span><input ref="picker" type="file" multiple :accept="accepted" @change="event=>addFiles((event.target as HTMLInputElement).files!)"/>
      </div>
      <div class="quality-files-heading"><strong>待校验文件</strong><span>{{ files.length }}</span></div>
      <div v-if="!files.length" class="quality-files-empty">尚未上传文件</div>
      <div class="quality-files">
        <button v-for="item in files" :key="item.id" :class="{active:activeId===item.id}" @click="activeId=item.id">
          <span class="quality-file-icon">{{ item.file.name.split('.').pop()?.toUpperCase() }}</span><span class="quality-file-info"><strong>{{ item.file.name }}</strong><small>{{ item.status==='parsing'?'解析中…':item.status==='error'?'解析失败':item.status==='ready'?'已就绪':'等待中' }} · {{ item.saveStatus==='saved'?'已保存':item.saveStatus==='save-error'?'保存失败':'保存中…' }}</small></span><i @click.stop="removeFile(item.id)">×</i>
        </button>
      </div>
    </aside>
    <main class="quality-right">
      <div v-if="!activeFile" class="quality-welcome"><div>✓</div><h2>石油工程数据智能质控</h2><p>请从左侧上传实验数据、工程报表或技术文档，系统将根据规则库、术语库和基础数据自动校验并标注。</p><div class="legend"><span class="legend-error">错误标红</span><span class="legend-warning">警告标黄</span><span class="legend-suggestion">建议下划线</span></div></div>
      <template v-else>
        <div class="quality-toolbar"><div><h2>{{ activeFile.file.name }}</h2><span>{{ activeFile.status==='ready'?'校验完成':activeFile.status==='parsing'?'正在解析文件…':activeFile.error }}</span></div><div class="quality-stats"><b class="error">{{ counts.error }}<small>错误</small></b><b class="warning">{{ counts.warning }}<small>警告</small></b><b class="suggestion">{{ counts.suggestion }}<small>建议</small></b></div></div>
        <div v-if="activeFile.status==='error'" class="parse-error">{{ activeFile.error }}</div>
        <div v-else-if="activeFile.status==='parsing'" class="quality-loading">正在解析并执行质控规则…</div>
        <div v-else class="quality-result">
          <section class="annotated-panel"><div class="panel-header"><strong>数据标注结果</strong><div class="legend small"><span class="legend-error">错误</span><span class="legend-warning">警告</span><span class="legend-suggestion">建议</span></div></div><div class="annotated-content"><template v-for="(segment,index) in segments" :key="index"><mark v-if="segment.level" :class="segment.level" :data-issue="segment.issueId" :title="levelLabel[segment.level]" @click="selectedIssue=segment.issueId!">{{ segment.text }}</mark><span v-else>{{ segment.text }}</span></template></div></section>
          <aside class="issue-panel"><div class="panel-header"><strong>发现的问题</strong><span>{{ issues.length }} 项</span></div><div v-if="!issues.length" class="no-issues">✓<strong>未发现典型问题</strong><span>当前内容已通过已启用规则检查</span></div><button v-for="issue in issues" v-else :key="issue.id" class="issue-card" :class="[issue.level,{active:selectedIssue===issue.id}]" @click="selectIssue(issue)"><span class="issue-level">{{ levelLabel[issue.level] }}</span><div><strong>{{ issue.title }} · {{ issue.ruleId }}</strong><p>{{ issue.message }}</p><small>{{ issue.suggestion }}</small></div></button></aside>
        </div>
      </template>
    </main>
  </section>
</template>
