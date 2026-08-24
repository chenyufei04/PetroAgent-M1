<script setup lang="ts">
import { computed, ref } from "vue";
import { termRecords } from "../data/seed";

const query=ref("");
const domain=ref("全部专业");
const status=ref("全部状态");
const domains=["全部专业",...Array.from(new Set(termRecords.map(x=>x.domain)))];
const normalized=computed(()=>query.value.trim().toLocaleLowerCase());
const results=computed(()=>termRecords.filter(item=>{
  const text=[item.id,item.zh,item.en,item.abbr,item.domain,item.subdomain,item.definition,item.unit,item.aliases.join(" "),item.source].join(" ").toLocaleLowerCase();
  return (!normalized.value||text.includes(normalized.value))&&(domain.value==="全部专业"||item.domain===domain.value)&&(status.value==="全部状态"||item.status===status.value);
}));
</script>

<template>
  <section class="data-page">
    <div class="data-heading"><div><h1>术语库</h1><p>石油工程规范术语、英文名称、缩写、定义和标准来源。</p></div><div class="result-count">共 <b>{{ results.length }}</b> 条术语</div></div>
    <div class="filter-bar">
      <div class="search-box"><span>⌕</span><input v-model="query" placeholder="模糊查询中文、英文、缩写、定义、别名或来源"/><button v-if="query" @click="query=''">×</button></div>
      <select v-model="domain"><option v-for="item in domains" :key="item">{{ item }}</option></select>
      <select v-model="status"><option>全部状态</option><option>已审核</option><option>待审核</option></select>
    </div>
    <div class="table-card">
      <table><thead><tr><th>编号</th><th>规范术语</th><th>英文/缩写</th><th>专业分类</th><th>定义</th><th>标准单位</th><th>来源</th><th>状态</th></tr></thead>
        <tbody><tr v-for="item in results" :key="item.id"><td class="mono">{{ item.id }}</td><td><strong>{{ item.zh }}</strong><small v-if="item.aliases.length">别名：{{ item.aliases.join('、') }}</small></td><td>{{ item.en }}<small v-if="item.abbr">{{ item.abbr }}</small></td><td>{{ item.domain }}<small>{{ item.subdomain }}</small></td><td class="definition">{{ item.definition }}</td><td>{{ item.unit||'—' }}</td><td>{{ item.source }}</td><td><span class="review-status" :class="item.status==='已审核'?'approved':'pending'">{{ item.status }}</span></td></tr></tbody>
      </table><div v-if="!results.length" class="table-empty">没有找到匹配的术语，请调整查询条件。</div>
    </div>
  </section>
</template>
