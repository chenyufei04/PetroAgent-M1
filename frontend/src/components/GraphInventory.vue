<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  graph: { type: Object, required: true },
});
const tab = ref("entities");
const search = ref("");
const text = (value) => String(value ?? "").toLowerCase();
const entities = computed(() =>
  props.graph.nodes.filter((node) =>
    [node.id, node.label, node.type].some((value) => text(value).includes(text(search.value)))
  )
);
const relationships = computed(() =>
  props.graph.edges.filter((edge) =>
    [edge.source_label, edge.source, edge.label, edge.relation_id, edge.target_label, edge.target]
      .some((value) => text(value).includes(text(search.value)))
  )
);
</script>

<template>
  <section class="graph-inventory">
    <div class="inventory-toolbar">
      <div>
        <button :class="{ active: tab === 'entities' }" @click="tab = 'entities'">
          全部实体（{{ graph.nodes.length }}）
        </button>
        <button :class="{ active: tab === 'relationships' }" @click="tab = 'relationships'">
          全部关系（{{ graph.edges.length }}）
        </button>
      </div>
      <input v-model="search" placeholder="搜索名称、ID或类型" />
    </div>
    <div class="inventory-table">
      <table v-if="tab === 'entities'">
        <thead><tr><th>实体名称</th><th>实体ID</th><th>类型</th><th>属性</th></tr></thead>
        <tbody>
          <tr v-for="node in entities" :key="node.id">
            <td>{{ node.label }}</td><td><code>{{ node.id }}</code></td><td>{{ node.type }}</td>
            <td><code>{{ JSON.stringify(node.properties || {}) }}</code></td>
          </tr>
        </tbody>
      </table>
      <table v-else>
        <thead><tr><th>起点实体</th><th>关系</th><th>终点实体</th><th>关系类型</th></tr></thead>
        <tbody>
          <tr v-for="edge in relationships" :key="edge.id">
            <td>{{ edge.source_label || edge.source }}</td><td>{{ edge.label }}</td>
            <td>{{ edge.target_label || edge.target }}</td><td><code>{{ edge.relation_id }}</code></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
