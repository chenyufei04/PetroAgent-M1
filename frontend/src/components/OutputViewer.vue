<script setup>
import { computed, ref, watch } from "vue";
import { getOutputPreview, outputUrl } from "../api";

const props = defineProps({
  files: { type: Array, default: () => [] },
});

const categories = [
  { id: "chart", label: "图表" },
  { id: "document", label: "文档" },
  { id: "table", label: "表格" },
];
const activeCategory = ref("chart");
const selected = ref(null);
const preview = ref(null);
const loading = ref(false);
const error = ref("");

const filteredFiles = computed(() =>
  props.files.filter((file) => file.display_category === activeCategory.value)
);

async function selectFile(file) {
  selected.value = file;
  preview.value = null;
  error.value = "";
  if (file.display_category === "chart") return;
  loading.value = true;
  try {
    preview.value = await getOutputPreview(file.preview_url);
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

watch(
  [() => props.files, activeCategory],
  () => {
    const first = filteredFiles.value[0] || null;
    selectFile(first);
  },
  { immediate: true, deep: true }
);
</script>

<template>
  <div class="output-viewer">
    <div class="output-tabs">
      <button
        v-for="category in categories"
        :key="category.id"
        :class="{ active: activeCategory === category.id }"
        @click="activeCategory = category.id"
      >
        {{ category.label }}
        <span>{{ files.filter((file) => file.display_category === category.id).length }}</span>
      </button>
    </div>

    <div class="output-layout">
      <nav class="output-files">
        <button
          v-for="file in filteredFiles"
          :key="file.download_url"
          :class="{ active: selected?.download_url === file.download_url }"
          @click="selectFile(file)"
        >
          <span>{{ file.type.toUpperCase() }}</span>
          {{ file.name }}
        </button>
        <p v-if="!filteredFiles.length">该分类暂无产物</p>
      </nav>

      <section class="preview-pane">
        <div v-if="selected" class="preview-heading">
          <strong>{{ selected.name }}</strong>
          <a :href="outputUrl(selected.download_url)" download>下载原文件</a>
        </div>
        <p v-if="loading" class="preview-empty">正在加载预览…</p>
        <p v-else-if="error" class="preview-error">{{ error }}</p>
        <img
          v-else-if="selected?.display_category === 'chart'"
          :src="outputUrl(selected.preview_url)"
          :alt="selected.name"
        />
        <div v-else-if="preview?.kind === 'table'" class="table-scroll">
          <table>
            <thead><tr><th v-for="column in preview.columns" :key="column">{{ column }}</th></tr></thead>
            <tbody>
              <tr v-for="(row, index) in preview.rows" :key="index">
                <td v-for="column in preview.columns" :key="column">{{ row[column] }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <pre v-else-if="preview?.format === 'json'">{{ JSON.stringify(preview.content, null, 2) }}</pre>
        <pre v-else-if="preview?.content">{{ preview.content }}</pre>
        <p v-else class="preview-empty">选择左侧产物进行预览</p>
      </section>
    </div>
  </div>
</template>
