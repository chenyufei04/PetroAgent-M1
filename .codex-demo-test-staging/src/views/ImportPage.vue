<script setup lang="ts">
import { computed, ref, type Ref } from "vue";
import { useDataStore } from "../stores/data";
import type { ImportFile } from "../types";

type ImportKind = "terms" | "rules";
interface ImportWorkspace {
  label: string;
  description: string;
  directory: Ref<FileSystemDirectoryHandle | undefined>;
  files: Ref<ImportFile[]>;
}

const extensions=[".doc",".docx",".xls",".xlsx",".csv",".tsv",".pdf",".txt",".md",".json",".xml",".rtf",".odt",".ods",".ppt",".pptx"];
const labels:Record<string,string>={doc:"Word 文档",docx:"Word 文档",xls:"Excel 表格",xlsx:"Excel 表格",csv:"CSV 数据",tsv:"TSV 数据",pdf:"PDF 文档",txt:"文本文件",md:"Markdown",json:"JSON 数据",xml:"XML 数据",rtf:"RTF 文档",odt:"OpenDocument",ods:"OpenDocument",ppt:"演示文稿",pptx:"演示文稿"};
const ext=(name:string)=>name.split(".").pop()?.toLowerCase()??"";
const formatSize=(bytes:number)=>bytes<1024?`${bytes} B`:bytes<1048576?`${(bytes/1024).toFixed(1)} KB`:`${(bytes/1048576).toFixed(1)} MB`;

const store=useDataStore();
const activeKind=ref<ImportKind>("terms");
const termDirectory=ref<FileSystemDirectoryHandle>();
const ruleDirectory=ref<FileSystemDirectoryHandle>();
const termFiles=ref<ImportFile[]>([]);
const ruleFiles=ref<ImportFile[]>([]);
const picker=ref<HTMLInputElement>();
const dragging=ref(false);
const messages=ref<Record<ImportKind,string>>({terms:"",rules:""});
const workspaces:Record<ImportKind,ImportWorkspace>={
  terms:{label:"术语导入",description:"导入石油工程术语表、词典或参考资料",directory:termDirectory,files:termFiles},
  rules:{label:"规则导入",description:"导入术语校验规则、质控标准或规则配置",directory:ruleDirectory,files:ruleFiles},
};
const current=computed(()=>workspaces[activeKind.value]);
const readyCount=computed(()=>current.value.files.value.filter(x=>x.status==="ready"||x.status==="error").length);

function switchKind(kind:ImportKind){activeKind.value=kind;dragging.value=false;}
async function chooseDirectory(){
  if(!window.showDirectoryPicker){messages.value[activeKind.value]="当前浏览器不支持直接选择本地目录，请使用最新版 Chrome 或 Edge。";return;}
  try{current.value.directory.value=await window.showDirectoryPicker({mode:"readwrite"});messages.value[activeKind.value]=`${current.value.label}保存目录已设置：${current.value.directory.value.name}`;}
  catch(error){if((error as DOMException).name!=="AbortError")messages.value[activeKind.value]="无法获得该目录的写入权限。";}
}
function add(input:FileList|File[]){
  const all=Array.from(input);const valid=all.filter(file=>extensions.includes(`.${ext(file.name)}`));const list=current.value.files.value;
  const seen=new Set(list.map(x=>`${x.file.name}-${x.file.size}-${x.file.lastModified}`));
  list.push(...valid.filter(file=>!seen.has(`${file.name}-${file.size}-${file.lastModified}`)).map(file=>({id:crypto.randomUUID(),file,category:labels[ext(file.name)]??"数据文件",status:"ready" as const})));
  messages.value[activeKind.value]=all.length>valid.length?`${all.length-valid.length} 个不支持的文件已忽略`:"";
  if(picker.value)picker.value.value="";
}
function onDrop(event:DragEvent){event.preventDefault();dragging.value=false;if(event.dataTransfer)add(event.dataTransfer.files);}
async function importFiles(){
  const kind=activeKind.value;const workspace=workspaces[kind];const ready=workspace.files.value.filter(x=>x.status==="ready"||x.status==="error");if(!ready.length)return;
  if(!workspace.directory.value){messages.value[kind]=`请先选择${workspace.label}的本地保存目录。`;return;}
  let saved=0;
  for(const item of ready){
    item.status="saving";
    try{const handle=await workspace.directory.value.getFileHandle(item.file.name,{create:true});const writable=await handle.createWritable();await writable.write(item.file);await writable.close();item.status="done";saved++;}
    catch{item.status="error";}
  }
  const successful=ready.filter(x=>x.status==="done");
  const amount=successful.reduce((sum,x)=>sum+Math.max(1,Math.round(x.file.size/8000)),0);
  store.addImported(kind==="terms"?amount:0,kind==="rules"?amount:0);
  messages.value[kind]=`${workspace.label}完成：已保存 ${saved}/${ready.length} 个文件，识别${kind==="terms"?"术语":"规则"} ${amount} 条。`;
}
function removeFile(id:string){current.value.files.value=current.value.files.value.filter(x=>x.id!==id);}
function clearCompleted(){current.value.files.value=current.value.files.value.filter(x=>x.status!=="done");}
</script>

<template>
  <section class="import-page">
    <div class="page-heading"><div><h1>数据导入</h1><p>术语与规则使用独立队列和本地目录，避免数据混存。</p></div></div>
    <div class="import-tabs" role="tablist">
      <button v-for="kind in (['terms','rules'] as ImportKind[])" :key="kind" :class="{active:activeKind===kind}" role="tab" @click="switchKind(kind)">
        <span>{{ workspaces[kind].label }}</span><b>{{ workspaces[kind].files.value.length }}</b>
      </button>
    </div>
    <div class="import-workspace">
      <div class="workspace-heading"><div><h2>{{ current.label }}</h2><p>{{ current.description }}</p></div><button class="primary" :disabled="!readyCount" @click="importFiles">开始导入</button></div>
      <div class="directory-card"><div><strong>{{ activeKind==='terms'?'术语':'规则' }}保存目录</strong><span>{{ current.directory.value ? current.directory.value.name : '尚未选择目录' }}</span></div><button class="secondary" @click="chooseDirectory">选择目录</button></div>
      <div class="drop-zone" :class="{dragging}" role="button" tabindex="0" @dragenter="dragging=true" @dragleave="dragging=false" @dragover.prevent @drop="onDrop" @click="picker?.click()" @keydown.enter="picker?.click()">
        <div class="upload-icon">⇧</div><strong>拖拽{{ activeKind==='terms'?'术语':'规则' }}文件到此处，或点击选择文件</strong><span>支持 Word、Excel、CSV、PDF、TXT、JSON、XML、Markdown、RTF、OpenDocument、PPT 等主流格式</span>
        <input ref="picker" type="file" multiple :accept="extensions.join(',')" @change="event=>add((event.target as HTMLInputElement).files!)" />
      </div>
      <div class="file-panel"><div class="panel-title"><div><strong>{{ current.label }}文件</strong><span>{{ current.files.value.length }} 个文件</span></div><button v-if="current.files.value.some(x=>x.status==='done')" class="text-button" @click="clearCompleted">清除已完成</button></div>
        <div v-if="!current.files.value.length" class="empty-list">尚未添加{{ activeKind==='terms'?'术语':'规则' }}文件</div>
        <div v-for="item in current.files.value" v-else :key="item.id" class="file-row"><div class="file-badge">{{ ext(item.file.name).toUpperCase() }}</div><div class="file-info"><strong>{{ item.file.name }}</strong><span>{{ item.category }} · {{ formatSize(item.file.size) }}</span></div><span class="status" :class="item.status">{{ item.status==='done'?'已保存':item.status==='saving'?'保存中':item.status==='error'?'失败':'待导入' }}</span><button class="remove" @click="removeFile(item.id)">删除</button></div>
      </div><div v-if="messages[activeKind]" class="message">{{ messages[activeKind] }}</div>
    </div>
  </section>
</template>
