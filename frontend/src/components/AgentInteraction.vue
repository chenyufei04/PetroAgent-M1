<script setup>
import { onMounted, ref } from "vue";
import { chatWithAssistant, getAssistantStatus } from "../api";

const props = defineProps({
  experimentId: { type: String, required: true },
  caseId: { type: String, required: true },
});
const emit = defineEmits(["display"]);
const question = ref("");
const messages = ref([]);
const loading = ref(false);
const error = ref("");
const status = ref(null);
const examples = ["为什么推荐当前方案？", "只看未通过规则和证据", "展示关键指标和图谱", "查看全部方案排名"];

async function send(text = question.value) {
  const content = text.trim();
  if (!content || loading.value) return;
  messages.value.push({ role: "user", content });
  question.value = "";
  loading.value = true;
  error.value = "";
  try {
    const response = await chatWithAssistant(props.experimentId, props.caseId, content);
    messages.value.push({ role: "assistant", content: response.answer, sources: response.sources });
    emit("display", response.display);
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try { status.value = await getAssistantStatus(); } catch { status.value = null; }
});
</script>

<template>
  <section class="agent-console panel">
    <div class="agent-heading">
      <div>
        <p class="panel-label">PETROAGENT · QWEN + RAG</p>
        <h2>交互式工程分析助手</h2>
      </div>
      <span v-if="status" class="model-badge">{{ status.model }} · {{ status.mode }}</span>
    </div>
    <div class="agent-layout">
      <div class="agent-intro">
        <p>告诉助手你要查看什么。回答会绑定当前实验方案，并自动组织页面区域。</p>
        <div class="agent-examples">
          <button v-for="item in examples" :key="item" @click="send(item)">{{ item }}</button>
        </div>
        <small>只读模式：模型不会修改规则、重算模拟结果或直接启动 OPM Flow。</small>
      </div>
      <div class="agent-chat">
        <div class="agent-messages">
          <p v-if="!messages.length" class="agent-placeholder">例如：为什么这个方案技术可行但经济未通过？</p>
          <article v-for="(item, index) in messages" :key="index" :class="item.role">
            <strong>{{ item.role === "user" ? "你" : "PetroAgent" }}</strong>
            <p>{{ item.content }}</p>
            <small v-if="item.sources">依据：{{ item.sources.map(source => source.id).filter(Boolean).join(" · ") }}</small>
          </article>
        </div>
        <form @submit.prevent="send()">
          <input v-model="question" :disabled="loading" placeholder="输入你希望分析或展示的内容……" />
          <button :disabled="loading || !question.trim()">{{ loading ? "分析中" : "发送" }}</button>
        </form>
        <p v-if="error" class="alert">{{ error }}</p>
      </div>
    </div>
  </section>
</template>
