<script setup>
import { computed, ref } from "vue";
import { getScenarioExplanation, outputUrl } from "../api";

const props = defineProps({ experiment: { type: Object, required: true } });
const oilEffect = computed(() => props.experiment.metric_effects.final_cumulative_oil_m3);
const pressureEffect = computed(() => props.experiment.metric_effects.final_field_pressure_bar);
const best = computed(() => props.experiment.best_cumulative_oil_case);
const comparison = computed(() => props.experiment.waterflood_comparison || null);
const bestIncrement = computed(() => comparison.value?.best_incremental_oil_case || null);
const economics = computed(() => props.experiment.techno_economics || null);
const rankedCases = computed(() => economics.value?.cases || []);
const bestEconomic = computed(() => rankedCases.value[0] || null);
const explanation = ref(null);
const explanationLoading = ref(false);
const explanationError = ref("");
const number = (value, digits = 0) => Number(value).toLocaleString("zh-CN", {
  maximumFractionDigits: digits,
  minimumFractionDigits: digits,
});
const loadExplanation = async (caseId) => {
  explanationLoading.value = true;
  explanationError.value = "";
  try {
    explanation.value = await getScenarioExplanation(props.experiment.experiment_id, caseId);
  } catch (error) {
    explanationError.value = error.message;
  } finally {
    explanationLoading.value = false;
  }
};
</script>

<template>
  <section class="panel experiment-panel">
    <div class="panel-heading">
      <div>
        <p class="panel-label">PARAMETER SWEEP · OPM FLOW</p>
        <h2>{{ experiment.experiment_id }} 敏感性分析</h2>
        <p class="experiment-lineage">
          关联案例：<strong>{{ experiment.analysis_case_id }}</strong>
          · {{ experiment.data_nature }}
        </p>
      </div>
      <span class="quality-badge" :class="experiment.quality.status">
        数据质量 {{ experiment.quality.status === "passed" ? "通过" : "需关注" }}
      </span>
    </div>

    <div class="experiment-kpis">
      <article><span>成功算例</span><strong>{{ experiment.quality.case_rows }} / {{ experiment.quality.case_rows }}</strong></article>
      <article><span>时间序列</span><strong>{{ number(experiment.quality.time_series_rows) }}</strong></article>
      <article><span>增注产油变化</span><strong>+{{ number(oilEffect.rate_100_to_200_percent, 1) }}%</strong><small>100 → 200 m³/day</small></article>
      <article><span>末期压力变化</span><strong>+{{ number(pressureEffect.rate_100_to_200_absolute, 2) }}</strong><small>bar，100 → 200 m³/day</small></article>
    </div>

    <p class="experiment-takeaway">
      注入速率是本轮累计产油、含水率和压力响应的主导因素。最大累计产油
      <strong>{{ number(best.final_cumulative_oil_m3, 1) }} m³</strong>，对应
      {{ best.parameter_polymer_concentration }} kg/m³ 和 {{ best.parameter_injection_rate }} m³/day；
      该处展示纯产量敏感性，技术经济筛选见下方方案排名。
    </p>

    <div class="experiment-figures">
      <figure v-for="figure in experiment.figures" :key="figure.file">
        <img :src="outputUrl(figure.url)" :alt="figure.name" />
        <figcaption>{{ figure.name }}</figcaption>
      </figure>
    </div>

    <div class="experiment-table-wrap">
      <table>
        <thead><tr><th>浓度 kg/m³</th><th>注入速率 m³/day</th><th>累计产油 m³</th><th>末期含水率</th><th>末期压力 bar</th></tr></thead>
        <tbody>
          <tr v-for="item in experiment.cases" :key="item.case_id">
            <td>{{ item.parameter_polymer_concentration }}</td>
            <td>{{ item.parameter_injection_rate }}</td>
            <td>{{ number(item.final_cumulative_oil_m3, 1) }}</td>
            <td>{{ number(item.final_water_cut_fraction, 4) }}</td>
            <td>{{ number(item.final_field_pressure_bar, 2) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="experiment-links">
      <a :href="outputUrl(experiment.report_url)" target="_blank">下载 Markdown 报告</a>
      <a :href="outputUrl(experiment.case_metrics_url)" target="_blank">下载指标 CSV</a>
    </div>

    <section v-if="comparison" class="comparison-section">
      <div class="panel-heading">
        <div>
          <p class="panel-label">PAIRED BASELINE · WATERFLOOD</p>
          <h2>水驱—聚合物驱成对增量评价</h2>
          <p class="experiment-lineage">
            基准实验：<strong>{{ comparison.waterflood_experiment_id }}</strong>
            · 按同一注入速率配对
          </p>
        </div>
        <span class="quality-badge" :class="comparison.quality.status">
          配对质量 {{ comparison.quality.status === "passed" ? "通过" : "需关注" }}
        </span>
      </div>

      <div class="experiment-kpis comparison-kpis">
        <article><span>成功配对</span><strong>{{ comparison.quality.paired_case_rows }} / 9</strong></article>
        <article><span>正增油方案</span><strong>{{ comparison.positive_increment_cases }} / 9</strong></article>
        <article><span>最大增量产油</span><strong>{{ number(bestIncrement.incremental_cumulative_oil_m3, 1) }}</strong><small>m³</small></article>
        <article><span>最大相对增幅</span><strong>{{ number(bestIncrement.incremental_oil_percent, 3) }}%</strong><small>{{ bestIncrement.parameter_injection_rate }} m³/day</small></article>
      </div>

      <p class="experiment-takeaway">
        仅 {{ comparison.positive_increment_cases }} / 9 个聚合物方案在末期超过同速率水驱，均位于
        200 m³/day。最大增量为
        <strong>{{ number(bestIncrement.incremental_cumulative_oil_m3, 1) }} m³</strong>，对应
        {{ bestIncrement.parameter_polymer_concentration }} kg/m³；该差值尚未计入药剂、能耗和产水处理成本。
      </p>

      <div class="experiment-figures comparison-figures">
        <figure v-for="figure in comparison.figures" :key="figure.file">
          <img :src="outputUrl(figure.url)" :alt="figure.name" />
          <figcaption>{{ figure.name }}</figcaption>
        </figure>
      </div>

      <div class="experiment-table-wrap">
        <table>
          <thead><tr><th>浓度 kg/m³</th><th>注入速率 m³/day</th><th>水驱累计油 m³</th><th>聚合物累计油 m³</th><th>增量油 m³</th><th>增幅</th><th>含水率差 pp</th><th>压力差 bar</th></tr></thead>
          <tbody>
            <tr v-for="item in comparison.cases" :key="item.polymer_case_id">
              <td>{{ item.parameter_polymer_concentration }}</td>
              <td>{{ item.parameter_injection_rate }}</td>
              <td>{{ number(item.final_cumulative_oil_m3_water, 1) }}</td>
              <td>{{ number(item.final_cumulative_oil_m3_polymer, 1) }}</td>
              <td :class="item.incremental_cumulative_oil_m3 >= 0 ? 'delta-positive' : 'delta-negative'">{{ number(item.incremental_cumulative_oil_m3, 1) }}</td>
              <td>{{ number(item.incremental_oil_percent, 3) }}%</td>
              <td>{{ number(item.water_cut_change_percentage_points, 3) }}</td>
              <td>{{ number(item.incremental_field_pressure_bar, 3) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="experiment-links">
        <a :href="outputUrl(comparison.report_url)" target="_blank">下载成对分析报告</a>
        <a :href="outputUrl(comparison.paired_case_metrics_url)" target="_blank">下载终值增量 CSV</a>
        <a :href="outputUrl(comparison.paired_time_series_url)" target="_blank">下载动态增量 CSV</a>
      </div>
    </section>

    <section v-if="economics && bestEconomic" class="comparison-section economics-section">
      <div class="panel-heading">
        <div>
          <p class="panel-label">TECHNO-ECONOMICS · CONSTRAINT SCREENING</p>
          <h2>聚合物方案技术经济排名</h2>
          <p class="experiment-lineage">
            模型：<strong>{{ economics.model_id }}</strong>
            · 假设状态 {{ economics.assumption_status }}
          </p>
        </div>
        <span class="quality-badge" :class="economics.economically_positive ? 'passed' : 'warning'">
          经济为正 {{ economics.economically_positive }} / {{ economics.case_count }}
        </span>
      </div>

      <div class="experiment-kpis economics-kpis">
        <article><span>技术可行</span><strong>{{ economics.technically_feasible }} / {{ economics.case_count }}</strong></article>
        <article><span>排名第一浓度</span><strong>{{ number(bestEconomic.polymer_concentration_kg_m3, 1) }}</strong><small>kg/m³</small></article>
        <article><span>排名第一注入率</span><strong>{{ number(bestEconomic.injection_rate_m3_day) }}</strong><small>m³/day</small></article>
        <article><span>排名第一净增量价值</span><strong :class="bestEconomic.net_incremental_value >= 0 ? 'delta-positive' : 'delta-negative'">{{ number(bestEconomic.net_incremental_value, 0) }}</strong><small>{{ bestEconomic.currency }}</small></article>
      </div>

      <p class="experiment-takeaway economics-warning">
        排名首先排除违反设施约束的方案，再优先选择经济为正方案，并按净增量价值排序。
        当前价格与约束为 <strong>illustrative_unvalidated</strong>，排名只能用于验证筛选流程。
      </p>

      <div class="experiment-table-wrap">
        <table>
          <thead><tr><th>排名</th><th>浓度 kg/m³</th><th>注入率 m³/day</th><th>聚合物 t</th><th>增量油 m³</th><th>净增量价值</th><th>技术可行</th><th>建议</th><th>解释</th></tr></thead>
          <tbody>
            <tr v-for="item in rankedCases" :key="item.polymer_case_id">
              <td><strong>#{{ item.scenario_rank }}</strong></td>
              <td>{{ number(item.polymer_concentration_kg_m3, 1) }}</td>
              <td>{{ number(item.injection_rate_m3_day) }}</td>
              <td>{{ number(item.polymer_mass_tonnes, 1) }}</td>
              <td :class="item.incremental_oil_m3 >= 0 ? 'delta-positive' : 'delta-negative'">{{ number(item.incremental_oil_m3, 1) }}</td>
              <td :class="item.net_incremental_value >= 0 ? 'delta-positive' : 'delta-negative'">{{ number(item.net_incremental_value, 0) }} {{ item.currency }}</td>
              <td>{{ item.technically_feasible ? '是' : '否' }}</td>
              <td>{{ item.recommendation }}</td>
              <td><button class="explanation-button" type="button" @click="loadExplanation(item.polymer_case_id)">查看依据</button></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="experiment-links">
        <a :href="outputUrl(economics.ranking_report_url)" target="_blank">下载排名报告</a>
        <a :href="outputUrl(economics.rankings_url)" target="_blank">下载排名 CSV</a>
        <a :href="outputUrl(economics.constraints_url)" target="_blank">下载约束明细</a>
        <a :href="outputUrl(economics.report_url)" target="_blank">下载经济报告</a>
      </div>

      <p v-if="explanationLoading" class="graph-message">正在加载规则解释链……</p>
      <p v-if="explanationError" class="alert">{{ explanationError }}</p>
      <section v-if="explanation" class="explanation-chain">
        <div class="panel-heading">
          <div>
            <p class="panel-label">EXPLAINABLE RECOMMENDATION</p>
            <h3>{{ explanation.case_id }}</h3>
          </div>
          <span class="quality-badge" :class="explanation.recommendation.decision === '优先候选' ? 'passed' : 'warning'">
            {{ explanation.recommendation.decision }}
          </span>
        </div>
        <p class="experiment-takeaway">{{ explanation.recommendation.rationale }}</p>
        <div class="explanation-columns">
          <article>
            <h4>指标绑定</h4>
            <ul>
              <li v-for="item in explanation.observations" :key="item.observation_id">
                <code>{{ item.concept_id }}</code><span>{{ number(item.value, 3) }} {{ item.unit }}</span>
              </li>
            </ul>
          </article>
          <article>
            <h4>规则执行</h4>
            <ul>
              <li v-for="item in explanation.rule_executions" :key="item.rule_execution_id">
                <span :class="item.passed ? 'delta-positive' : 'delta-negative'">{{ item.passed ? '通过' : '未通过' }}</span>
                <code>{{ item.rule_id }}</code><span>{{ item.message }}</span>
              </li>
            </ul>
          </article>
        </div>
        <p class="evidence-line">证据：{{ explanation.evidence.source_id }} · {{ explanation.evidence.assumption_status }}</p>
      </section>
    </section>
  </section>
</template>
