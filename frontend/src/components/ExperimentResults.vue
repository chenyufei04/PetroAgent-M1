<script setup>
import { computed } from "vue";
import { outputUrl } from "../api";

const props = defineProps({ experiment: { type: Object, required: true } });
const oilEffect = computed(() => props.experiment.metric_effects.final_cumulative_oil_m3);
const pressureEffect = computed(() => props.experiment.metric_effects.final_field_pressure_bar);
const best = computed(() => props.experiment.best_cumulative_oil_case);
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
      <article><span>成功算例</span><strong>{{ experiment.quality.case_rows }} / 9</strong></article>
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
  </section>
</template>
