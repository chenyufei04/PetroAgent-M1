<script setup>
import { nextTick, onMounted, ref, watch } from "vue";
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
const messagesPane = ref(null);
const examples = ["为什么推荐当前方案？", "只看未通过规则和证据", "展示关键指标和图谱", "查看全部方案排名"];

async function send(text = question.value) {
  const content = text.trim();
  if (!content || loading.value) return;
  messages.value.push({ role: "user", content });
  // 只发送当前问题之前的最近历史，避免当前 user 消息在请求中重复。
  const history = messages.value.slice(0, -1).slice(-10).map(({ role, content: itemContent }) => ({
    role,
    content: itemContent,
  }));
  question.value = "";
  loading.value = true;
  error.value = "";
  try {
    const response = await chatWithAssistant(props.experimentId, props.caseId, content, history);
    const previous = messages.value[messages.value.length - 1];
    // 防止网络重试或重复点击产生完全相同的相邻助手气泡。
    if (previous?.role !== "assistant" || previous.content !== response.answer) {
      messages.value.push({ role: "assistant", content: response.answer, sources: response.sources });
    }
    emit("display", response.display);
    await nextTick();
    if (messagesPane.value) messagesPane.value.scrollTop = messagesPane.value.scrollHeight;
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

function clearConversation() {
  messages.value = [];
  error.value = "";
}

// 不同方案具有不同工程事实，切换方案时清空历史，防止上下文串案。
watch(() => props.caseId, clearConversation);

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
      <div class="agent-actions">
        <span v-if="status" class="model-badge">{{ status.model }} · {{ status.mode }}</span>
        <button v-if="messages.length" type="button" class="clear-chat" @click="clearConversation">清空对话</button>
      </div>
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
        <div ref="messagesPane" class="agent-messages">
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
