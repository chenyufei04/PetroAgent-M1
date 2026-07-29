<script setup>
import { computed, onMounted, ref } from "vue";
import { getCases, getGraphView, getSubgraph, runAnalysis } from "./api";
import KnowledgeGraph from "./components/KnowledgeGraph.vue";
import GraphInventory from "./components/GraphInventory.vue";
import OutputViewer from "./components/OutputViewer.vue";

const cases = ref([]);
const selectedCase = ref("");
const result = ref(null);
const graph = ref({ status: "idle", nodes: [], edges: [] });
const loading = ref(false);
const error = ref("");
const selectedConcept = ref("");
const graphLoading = ref(false);
const graphView = ref("all");

const graphViews = [
  { id: "all", label: "全部图谱" },
  { id: "concepts", label: "概念关系" },
  { id: "rules", label: "规则概念" },
  { id: "sources", label: "规则证据" },
  { id: "stages", label: "阶段规则" },
];

const failedResults = computed(() =>
  result.value?.results.filter((item) => !item.passed) || []
);

async function loadCases() {
  cases.value = await getCases();
  selectedCase.value = cases.value.find((item) => item.runnable)?.case_id || "";
}

async function run() {
  if (!selectedCase.value) return;
  loading.value = true;
  error.value = "";
  selectedConcept.value = "";
  try {
    result.value = await runAnalysis(selectedCase.value);
    graph.value = await getSubgraph(result.value.concept_ids);
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

function selectFinding(item) {
  selectedConcept.value = item.concept_id || "";
}

async function loadGraph(view = graphView.value) {
  graphLoading.value = true;
  error.value = "";
  selectedConcept.value = "";
  try {
    graphView.value = view;
    graph.value = await getGraphView(view);
  } catch (err) {
    error.value = err.message;
  } finally {
    graphLoading.value = false;
  }
}

onMounted(async () => {
  try {
    await Promise.all([loadCases(), loadGraph("all")]);
  } catch (err) {
    error.value = err.message;
  }
});
</script>

<template>
  <main>
    <header>
      <div>
        <p class="eyebrow">POLYMER FLOODING · TRACEABLE ANALYSIS</p>
        <h1>PetroAgent 科研分析工作台</h1>
        <p class="subtitle">把确定性分析输出、规则证据和 Neo4j 知识路径放在同一视图中。</p>
      </div>
      <span class="status" :class="graph.status">
        Neo4j {{ graph.status === "online" ? "在线" : graph.status === "offline" ? "离线" : "待检测" }}
      </span>
    </header>

    <p v-if="error" class="alert">{{ error }}</p>

    <section class="workspace">
      <aside class="panel case-panel">
        <p class="panel-label">01 · 案例输入</p>
        <h2>演示案例</h2>
        <label for="case">选择案例</label>
        <select id="case" v-model="selectedCase">
          <option v-for="item in cases" :key="item.case_id" :value="item.case_id" :disabled="!item.runnable">
            {{ item.case_name }}{{ item.runnable ? "" : "（缺少数据）" }}
          </option>
        </select>
        <button :disabled="loading || !selectedCase" @click="run">
          {{ loading ? "分析运行中…" : "运行分析" }}
        </button>
        <div v-if="result" class="case-meta">
          <div><span>领域</span><strong>{{ result.case.domain }}</strong></div>
          <div><span>过程</span><strong>{{ result.case.process }}</strong></div>
          <div><span>数据行</span><strong>{{ result.summary.data_rows }}</strong></div>
          <div><span>规则模式</span><strong>{{ result.case.metadata.rule_execution.mode }}</strong></div>
        </div>
      </aside>

      <section class="main-column">
        <div class="summary-grid">
          <article><span>执行规则</span><strong>{{ result?.summary.total_rules ?? "—" }}</strong></article>
          <article><span>通过</span><strong class="good">{{ result?.summary.passed_rules ?? "—" }}</strong></article>
          <article><span>未通过</span><strong class="bad">{{ result?.summary.failed_rules ?? "—" }}</strong></article>
          <article><span>警告</span><strong class="warn">{{ result?.summary.warnings ?? "—" }}</strong></article>
        </div>

        <div class="panel results-panel">
          <div class="panel-heading">
            <div><p class="panel-label">02 · 分析结果</p><h2>规则执行与证据</h2></div>
            <span>{{ failedResults.length }} 项需关注</span>
          </div>
          <div v-if="!result" class="empty-state">选择案例并运行分析后，在此查看结构化结果。</div>
          <div v-else class="finding-list">
            <button
              v-for="item in result.results"
              :key="item.rule_id"
              class="finding"
              :class="{ failed: !item.passed }"
              @click="selectFinding(item)"
            >
              <span class="finding-state">{{ item.passed ? "通过" : item.severity }}</span>
              <span class="finding-body">
                <strong>{{ item.rule_id }}</strong>
                <span>{{ item.message }}</span>
                <small v-if="item.source_name || item.source_id">
                  证据：{{ item.source_name || item.source_id }}
                </small>
              </span>
              <span class="finding-value">{{ item.observed ?? "—" }}</span>
            </button>
          </div>
        </div>
      </section>

      <aside class="panel graph-panel">
        <div class="panel-heading">
          <div><p class="panel-label">03 · 知识图谱</p><h2>Neo4j 查询工作台</h2></div>
          <span>{{ graph.nodes.length }} 节点 · {{ graph.edges.length }} 关系</span>
        </div>
        <div class="graph-toolbar">
          <button
            v-for="item in graphViews"
            :key="item.id"
            class="graph-query-button"
            :class="{ active: graphView === item.id }"
            :disabled="graphLoading"
            @click="loadGraph(item.id)"
          >
            {{ item.label }}
          </button>
          <button class="graph-query-button refresh" :disabled="graphLoading" @click="loadGraph()">
            {{ graphLoading ? "查询中…" : "刷新" }}
          </button>
        </div>
        <KnowledgeGraph :graph="graph" :highlighted="selectedConcept" />
        <GraphInventory v-if="graphView === 'all' && graph.status === 'online'" :graph="graph" />
        <p v-if="graph.message" class="graph-message">{{ graph.message }}</p>
      </aside>
    </section>

    <section v-if="result" class="panel outputs-panel">
      <div class="panel-heading">
        <div><p class="panel-label">04 · 输出文件</p><h2>可视化预览与下载</h2></div>
        <span>图表 / 文档 / 表格</span>
      </div>
      <OutputViewer :files="result.output_files" />
    </section>
  </main>
</template>
