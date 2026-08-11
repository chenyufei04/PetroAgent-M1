<script setup>
import { computed, ref, watch } from "vue";
import { getScenarioContext, outputUrl } from "../api";
import KnowledgeGraph from "./KnowledgeGraph.vue";
import AgentInteraction from "./AgentInteraction.vue";

const props = defineProps({ experiment: { type: Object, required: true } });
const selectedCaseId = ref("");
const context = ref(null);
const loading = ref(false);
const error = ref("");
const selectedNode = ref(null);
const activeView = ref("evidence");
const visibleSections = ref(["overview", "metrics", "rules", "graph", "charts", "ranking", "evidence"]);
// 首次进入只呈现助手；收到展示指令后再展开实验工作台，减少首屏信息负担。
const workbenchVisible = ref(false);

// 多领域适配说明：候选方案来自后端排名契约，组件不依赖某个领域的参数名称。
const scenarios = computed(() => props.experiment.techno_economics?.cases || []);
const scenarioId = (item) => item.polymer_case_id || item.case_id || item.scenario_id || "";
const currentScenario = computed(() => context.value?.scenario || {});
const recommendation = computed(() => context.value?.recommendation || {});
const rules = computed(() => context.value?.rules || []);
const failedRules = computed(() => rules.value.filter((item) => !item.passed));
const observations = computed(() => [
  ...(context.value?.parameters || []),
  ...(context.value?.metrics || []),
]);
const selectedDetail = computed(() => selectedNode.value?.properties || null);

const number = (value, digits = 2) => {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits });
};

async function selectScenario(caseId) {
  if (!caseId) return;
  selectedCaseId.value = caseId;
  loading.value = true;
  error.value = "";
  selectedNode.value = null;
  try {
    context.value = await getScenarioContext(props.experiment.experiment_id, caseId);
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

function selectRule(rule) {
  selectedNode.value = { type: "RuleExecution", properties: rule };
}

function selectObservation(item) {
  selectedNode.value = { type: "MetricObservation", properties: item };
}

function applyAssistantDisplay(display) {
  // 模型只能选择预定义页面区域，不能注入组件、HTML 或任意 API 调用。
  if (display?.selected_case_id && display.selected_case_id !== selectedCaseId.value) {
    selectScenario(display.selected_case_id);
  }
  if (Array.isArray(display?.sections) && display.sections.length) {
    workbenchVisible.value = true;
    visibleSections.value = [...new Set(["overview", ...display.sections])];
    if (display.sections.includes("ranking") && !display.sections.includes("charts")) activeView.value = "ranking";
    if (display.sections.includes("charts")) activeView.value = "evidence";
  }
}

function resetAssistantWorkspace() {
  // 恢复首次进入状态：保留当前方案上下文缓存，但隐藏所有实验分析区域。
  workbenchVisible.value = false;
  selectedNode.value = null;
  visibleSections.value = ["overview", "metrics", "rules", "graph", "charts", "ranking", "evidence"];
  activeView.value = "evidence";
}

watch(
  () => props.experiment.experiment_id,
  () => {
    workbenchVisible.value = false;
    selectScenario(scenarioId(scenarios.value[0] || {}));
  },
  { immediate: true },
);
</script>

<template>
  <section class="scenario-workbench" :class="{ 'assistant-first': !workbenchVisible }">
    <AgentInteraction
      v-if="selectedCaseId"
      :experiment-id="experiment.experiment_id"
      :case-id="selectedCaseId"
      @display="applyAssistantDisplay"
      @reset="resetAssistantWorkspace"
    />
    <template v-if="workbenchVisible">
    <div class="workbench-header panel">
      <div>
        <p class="panel-label">SCENARIO DECISION WORKBENCH</p>
        <h2>{{ experiment.experiment_id }}</h2>
        <p>当前实验方案是指标、图表、规则、推荐与知识证据的唯一联动上下文。</p>
      </div>
      <label>
        <span>当前方案</span>
        <select :value="selectedCaseId" @change="selectScenario($event.target.value)">
          <option v-for="item in scenarios" :key="scenarioId(item)" :value="scenarioId(item)">
            #{{ item.scenario_rank }} · {{ scenarioId(item) }} · {{ item.recommendation }}
          </option>
        </select>
      </label>
      <button type="button" class="collapse-workbench" @click="workbenchVisible = false">收起分析区</button>
    </div>

    <p v-if="error" class="alert">{{ error }}</p>
    <div v-if="loading && !context" class="panel empty-state">正在加载方案上下文……</div>

    <template v-if="context">
      <section v-if="visibleSections.includes('overview')" class="decision-strip">
        <article class="decision-card panel">
          <span>推荐结论</span>
          <strong>{{ recommendation.decision || currentScenario.recommendation }}</strong>
          <small>{{ recommendation.rationale || "由规则执行结果生成" }}</small>
        </article>
        <article class="metric-card panel">
          <span>方案排名</span><strong>#{{ currentScenario.scenario_rank ?? "—" }}</strong>
          <small>确定性排序结果</small>
        </article>
        <article class="metric-card panel">
          <span>净增量价值</span>
          <strong :class="currentScenario.net_incremental_value >= 0 ? 'delta-positive' : 'delta-negative'">
            {{ number(currentScenario.net_incremental_value, 0) }} {{ currentScenario.currency || "" }}
          </strong>
          <small>{{ currentScenario.assumption_status || context.evidence.assumption_status }}</small>
        </article>
        <article class="metric-card panel">
          <span>规则通过</span><strong>{{ context.rule_summary.passed }} / {{ context.rule_summary.total }}</strong>
          <small v-if="failedRules.length" class="delta-negative">{{ failedRules.length }} 条未通过</small>
          <small v-else class="delta-positive">全部通过</small>
        </article>
      </section>

      <section v-if="visibleSections.includes('metrics') || visibleSections.includes('rules')" class="context-grid">
        <div v-if="visibleSections.includes('metrics')" class="panel context-metrics">
          <div class="panel-heading">
            <div><p class="panel-label">01 · CURRENT SCENARIO</p><h2>参数与工程指标</h2></div>
            <span>{{ observations.length }} 项观测</span>
          </div>
          <div class="observation-grid">
            <button v-for="item in observations" :key="item.observation_id" @click="selectObservation(item)">
              <span>{{ item.concept_id }}</span>
              <strong>{{ number(item.value, 3) }}</strong>
              <small>{{ item.unit }}</small>
            </button>
          </div>
        </div>

        <div v-if="visibleSections.includes('rules')" class="panel context-rules">
          <div class="panel-heading">
            <div><p class="panel-label">02 · RULE EXECUTION</p><h2>规则验证</h2></div>
            <span>{{ failedRules.length }} 项需关注</span>
          </div>
          <div class="rule-list">
            <button v-for="item in rules" :key="item.rule_execution_id" :class="{ failed: !item.passed }" @click="selectRule(item)">
              <span>{{ item.passed ? "通过" : "未通过" }}</span>
              <strong>{{ item.rule_id }}</strong>
              <small>{{ item.message }}</small>
            </button>
          </div>
        </div>
      </section>

      <section v-if="visibleSections.includes('graph') || visibleSections.includes('evidence')" class="panel explanation-graph-panel">
        <div class="panel-heading">
          <div><p class="panel-label">03 · EXPLANATION GRAPH</p><h2>当前方案解释链</h2></div>
          <span>{{ context.graph.nodes.length }} 节点 · {{ context.graph.edges.length }} 关系</span>
        </div>
        <div class="explanation-layout">
          <KnowledgeGraph
            :graph="context.graph"
            :highlighted="selectedNode?.id || ''"
            @node-select="selectedNode = $event"
          />
          <aside class="node-inspector">
            <template v-if="selectedDetail">
              <p class="panel-label">{{ selectedNode.type }}</p>
              <h3>{{ selectedDetail.rule_id || selectedDetail.concept_id || selectedDetail.decision || selectedDetail.source_id }}</h3>
              <dl>
                <template v-for="(value, key) in selectedDetail" :key="key">
                  <dt>{{ key }}</dt><dd>{{ Array.isArray(value) ? value.join("、") : value }}</dd>
                </template>
              </dl>
            </template>
            <template v-else>
              <p class="panel-label">EVIDENCE</p>
              <h3>{{ context.evidence.source_id || "方案证据" }}</h3>
              <p>点击指标、规则或图谱节点，在这里查看实际值、阈值、来源与推荐关系。</p>
              <small>数据来源：{{ context.provenance.source }} · 模型：{{ context.provenance.model_id || context.evidence.model_id }}</small>
            </template>
          </aside>
        </div>
      </section>

      <section v-if="visibleSections.includes('charts') || visibleSections.includes('ranking')" class="panel supporting-analysis">
        <div class="panel-heading">
          <div><p class="panel-label">04 · SUPPORTING ANALYSIS</p><h2>实验图表与方案对比</h2></div>
          <div class="view-tabs">
            <button :class="{ active: activeView === 'evidence' }" @click="activeView = 'evidence'">分析图表</button>
            <button :class="{ active: activeView === 'ranking' }" @click="activeView = 'ranking'">全部方案</button>
          </div>
        </div>
        <div v-if="activeView === 'evidence'" class="experiment-figures">
          <figure v-for="figure in experiment.figures" :key="figure.file">
            <img :src="outputUrl(figure.url)" :alt="figure.name" />
            <figcaption>{{ figure.name }} · 当前方案 {{ selectedCaseId }}</figcaption>
          </figure>
        </div>
        <div v-else class="experiment-table-wrap">
          <table>
            <thead><tr><th>排名</th><th>方案</th><th>推荐</th><th>净增量价值</th><th>技术可行</th></tr></thead>
            <tbody>
              <tr v-for="item in scenarios" :key="scenarioId(item)" :class="{ 'selected-row': scenarioId(item) === selectedCaseId }" @click="selectScenario(scenarioId(item))">
                <td>#{{ item.scenario_rank }}</td><td>{{ scenarioId(item) }}</td><td>{{ item.recommendation }}</td>
                <td>{{ number(item.net_incremental_value, 0) }} {{ item.currency }}</td><td>{{ item.technically_feasible ? "是" : "否" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
    </template>
  </section>
</template>
