<script setup lang="ts">
import { computed, watch } from "vue";
import { useRoute } from "vue-router";
import { pages } from "./router";
import { useDataStore } from "./stores/data";

const route = useRoute();
const store = useDataStore();
const activeName = computed(() => route.name as string);
watch(() => route.meta.label, label => { document.title = `${String(label)} - 石油工程术语质控`; }, { immediate: true });
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand" to="/quality">石油工程术语质控</RouterLink>
      <nav class="nav" aria-label="主导航">
        <RouterLink v-for="page in pages" :key="page.name" :class="{ active: activeName === page.name }" :to="page.path">{{ page.label }}</RouterLink>
      </nav>
      <div class="stats" aria-label="数据统计"><span>术语 <b>{{ store.termCount }}</b> 条</span><i /><span>规则 <b>{{ store.ruleCount }}</b> 条</span></div>
    </header>
    <main class="workspace"><RouterView /></main>
  </div>
</template>
