<script setup lang="ts">
import { computed, ref } from "vue";
import { baseRecords, type BaseRecord } from "../data/seed";

const types:BaseRecord["type"][]=["专业分类","计量单位","常用缩写","数据来源"];
const activeType=ref<BaseRecord["type"]>("专业分类");
const query=ref("");
const results=computed(()=>{const keyword=query.value.trim().toLocaleLowerCase();return baseRecords.filter(item=>item.type===activeType.value&&(!keyword||[item.id,item.name,item.code,item.description,item.parent].join(" ").toLocaleLowerCase().includes(keyword)));});
const count=(type:BaseRecord["type"])=>baseRecords.filter(x=>x.type===type).length;
</script>

<template>
  <section class="data-page">
    <div class="data-heading"><div><h1>基础数据</h1><p>维护术语质控使用的专业分类、计量单位、缩写和权威来源。</p></div><div class="result-count">当前 <b>{{ results.length }}</b> 条</div></div>
    <div class="base-layout">
      <aside class="base-menu"><button v-for="type in types" :key="type" :class="{active:activeType===type}" @click="activeType=type"><span>{{ type }}</span><b>{{ count(type) }}</b></button></aside>
      <div class="base-content">
        <div class="filter-bar compact"><div class="search-box"><span>⌕</span><input v-model="query" :placeholder="`模糊查询${activeType}名称、编码或说明`"/><button v-if="query" @click="query=''">×</button></div></div>
        <div class="table-card"><table><thead><tr><th>编号</th><th>名称</th><th>编码/符号</th><th>所属分类</th><th>说明</th><th>状态</th></tr></thead><tbody>
          <tr v-for="item in results" :key="item.id"><td class="mono">{{ item.id }}</td><td><strong>{{ item.name }}</strong></td><td><code>{{ item.code }}</code></td><td>{{ item.parent }}</td><td class="definition">{{ item.description }}</td><td><span class="review-status approved">{{ item.status }}</span></td></tr>
        </tbody></table><div v-if="!results.length" class="table-empty">没有找到匹配的基础数据。</div></div>
      </div>
    </div>
  </section>
</template>
