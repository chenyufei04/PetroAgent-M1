<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import cytoscape from "cytoscape";

const props = defineProps({
  graph: { type: Object, required: true },
  highlighted: { type: String, default: "" },
});
const container = ref(null);
let cy;
let resizeObserver;

async function render() {
  // graph.nodes 从空数组变为有数据时，v-if 对应的容器需要等到下一次
  // DOM 更新后才存在，否则 Cytoscape 会因为拿不到 container 而跳过渲染。
  await nextTick();
  if (!container.value) return;
  cy?.destroy();
  const elements = [
    ...props.graph.nodes.map((node) => ({ data: node })),
    ...props.graph.edges.map((edge) => ({ data: edge })),
  ];
  cy = cytoscape({
    container: container.value,
    elements,
    layout: { name: "cose", animate: false, padding: 28 },
    style: [
      {
        selector: "node",
        style: {
          label: "data(label)",
          "background-color": "#0f766e",
          color: "#173b3a",
          "font-size": 11,
          "text-valign": "bottom",
          "text-margin-y": 7,
          width: 34,
          height: 34,
        },
      },
      {
        selector: 'node[type = "Rule"]',
        style: { "background-color": "#2563eb", shape: "round-rectangle" },
      },
      {
        selector: 'node[type = "Source"]',
        style: { "background-color": "#7c3aed", shape: "diamond" },
      },
      {
        selector: 'node[type = "Stage"]',
        style: { "background-color": "#ea580c", shape: "hexagon" },
      },
      {
        selector: "edge",
        style: {
          label: "data(label)",
          width: 1.4,
          "line-color": "#94a3b8",
          "target-arrow-color": "#94a3b8",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          "font-size": 9,
          "text-background-color": "#fff",
          "text-background-opacity": 0.85,
        },
      },
      {
        selector: ".highlighted",
        style: {
          "background-color": "#f59e0b",
          width: 48,
          height: 48,
          "border-width": 4,
          "border-color": "#fef3c7",
        },
      },
    ],
  });
  cy.ready(() => {
    cy.resize();
    cy.fit(undefined, 36);
  });
  highlight();
}

function highlight() {
  if (!cy) return;
  cy.nodes().removeClass("highlighted");
  if (props.highlighted) cy.getElementById(props.highlighted).addClass("highlighted");
}

watch(() => props.graph, render, { deep: true, flush: "post" });
watch(() => props.highlighted, highlight);
onMounted(() => {
  render();
  resizeObserver = new ResizeObserver(() => {
    if (!cy) return;
    cy.resize();
    cy.fit(undefined, 36);
  });
  if (container.value) resizeObserver.observe(container.value);
});
watch(container, (current, previous) => {
  if (previous) resizeObserver?.unobserve(previous);
  if (current) resizeObserver?.observe(current);
}, { flush: "post" });
onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  cy?.destroy();
});
</script>

<template>
  <div v-if="graph.nodes.length" ref="container" class="graph-canvas"></div>
  <div v-else class="empty-state">暂无可显示的案例相关子图</div>
</template>
