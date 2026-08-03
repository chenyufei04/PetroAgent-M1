<script setup>
import { computed } from "vue";
import { outputUrl } from "../api";

const props = defineProps({ experiment: { type: Object, required: true } });
const oilEffect = computed(() => props.experiment.metric_effects.final_cumulative_oil_m3);
const pressureEffect = computed(() => props.experiment.metric_effects.final_field_pressure_bar);
const best = computed(() => props.experiment.best_cumulative_oil_case);
const comparison = computed(() => props.experiment.waterflood_comparison || null);
const bestIncrement = computed(() => comparison.value?.best_incremental_oil_case || null);
const number = (value, digits = 0) => Number(value).toLocaleString("zh-CN", {
  maximumFractionDigits: digits,
  minimumFractionDigits: digits,
});
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
      该结论尚未计入聚合物成本与压力约束。
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
  </section>
</template>
