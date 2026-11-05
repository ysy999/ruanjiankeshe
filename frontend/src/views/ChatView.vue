<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { apiFetch } from "@/api/client";
import SessionSidebar from "@/components/SessionSidebar.vue";
import { useSessionStore, type SessionItem } from "@/stores/sessions";

type Citation = { doc_name?: string; snippet?: string };
type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  citationsOpen: boolean;
  feedbackScore?: number;
  feedbackSending?: boolean;
  errorMessage?: string;
};

const sessionStore = useSessionStore();
const draft = ref("");
const sending = ref(false);
const messages = ref<ChatMessage[]>([]);
const scrollbar = ref<{ setScrollTop: (top: number) => void }>();
let nextId = 1;

async function selectSession(session: SessionItem) {
  if (sending.value) return;
  sessionStore.setCurrentSession(session.id);
  try {
    const history = await sessionStore.fetchMessages(session.id);
    messages.value = history.filter((item) => item.role !== "system").map((item) => ({
      id: typeof item.id === "number" ? item.id : nextId++,
      role: item.role === "user" ? "user" : "assistant",
      content: item.content,
      citations: item.citations ?? [],
      citationsOpen: false,
    }));
    await scrollToBottom();
  } catch (error) {
    messages.value = [];
    ElMessage.error(error instanceof Error ? error.message : "加载会话消息失败");
  }
}

async function initializeSessions() {
  try {
    await sessionStore.fetchSessions();
    const current = sessionStore.sessions.find((item) => String(item.id) === String(sessionStore.currentSessionId))
      ?? sessionStore.sessions[0];
    if (current) await selectSession(current);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载会话列表失败");
  }
}

function onSessionCreated() {
  messages.value = [];
}

onMounted(() => void initializeSessions());

async function scrollToBottom() {
  await nextTick();
  scrollbar.value?.setScrollTop(Number.MAX_SAFE_INTEGER);
}

function parsePayload(raw: string): unknown {
  const value = raw.trim();
  if (!value || value === "[DONE]") return value;
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return value;
  }
}

function applyEvent(type: string, payload: unknown, assistant: ChatMessage) {
  const data = payload && typeof payload === "object" ? payload as Record<string, unknown> : {};
  if (type === "delta") {
    const delta = typeof payload === "string" ? payload : data.delta ?? data.content ?? data.text;
    if (typeof delta === "string") assistant.content += delta;
  } else if (type === "citations") {
    const items = Array.isArray(payload) ? payload : data.citations;
    if (Array.isArray(items)) {
      assistant.citations = items as Citation[];
      assistant.citationsOpen = true;
    }
  } else if (type === "error") {
    assistant.errorMessage = String(typeof payload === "string" ? payload : data.msg ?? data.message ?? "对话请求失败");
    assistant.content = assistant.content || assistant.errorMessage;
  } else if (type === "done" && typeof data.message_id === "number") {
    assistant.id = data.message_id;
  }
}

async function sendFeedback(item: ChatMessage, score: number) {
  if (item.feedbackSending || item.feedbackScore != null || sessionStore.currentSessionId == null) return;
  item.feedbackSending = true;
  try {
    const response = await apiFetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionStore.currentSessionId, message_id: item.id, score }),
    });
    if (!response.ok) throw new Error(`提交反馈失败（HTTP ${response.status}）`);
    item.feedbackScore = score;
    ElMessage.success("感谢你的反馈");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "提交反馈失败");
  } finally {
    item.feedbackSending = false;
  }
}

async function sendMessage() {
  const message = draft.value.trim();
  if (!message || sending.value) return;
  if (sessionStore.currentSessionId == null) {
    ElMessage.warning("请先新建会话");
    return;
  }
  draft.value = "";
  const userMessage: ChatMessage = { id: nextId++, role: "user", content: message, citations: [], citationsOpen: false };
  const assistant: ChatMessage = { id: nextId++, role: "assistant", content: "", citations: [], citationsOpen: false };
  messages.value.push(userMessage, assistant);
  sending.value = true;
  await scrollToBottom();

  try {
    const response = await apiFetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ session_id: sessionStore.currentSessionId, message }),
    });
    if (!response.ok) throw new Error(`请求失败（HTTP ${response.status}）`);
    if (!response.body) throw new Error("浏览器未提供流式响应");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let done = false;
    while (!done) {
      const chunk = await reader.read();
      done = chunk.done;
      buffer += decoder.decode(chunk.value, { stream: !done }).replace(/\r\n/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        let eventType = "message";
        const dataLines: string[] = [];
        for (const line of frame.split("\n")) {
          if (line.startsWith("event:")) eventType = line.slice(6).trim();
          else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
        }
        if (dataLines.length) {
          const payload = parsePayload(dataLines.join("\n"));
          if (eventType === "done" || payload === "[DONE]") {
            // Stream completion is also handled by the HTTP stream ending.
          } else {
            applyEvent(eventType, payload, assistant);
            await scrollToBottom();
          }
        }
        boundary = buffer.indexOf("\n\n");
      }
    }
    if (buffer.trim()) {
      const dataLine = buffer.split("\n").find((line) => line.startsWith("data:"));
      if (dataLine) applyEvent("message", parsePayload(dataLine.slice(5)), assistant);
    }
    if (!assistant.content && !assistant.citations.length) assistant.content = "（没有收到回复内容）";
  } catch (error) {
    const messageText = error instanceof Error ? error.message : "发送失败，请稍后重试";
    assistant.content = assistant.content ? `${assistant.content}\n\n[${messageText}]` : messageText;
    assistant.errorMessage = messageText;
    ElMessage.error(messageText);
  } finally {
    sending.value = false;
    await scrollToBottom();
  }
}

function onInputKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    void sendMessage();
  }
}
</script>

<template>
  <main class="chat-layout">
    <SessionSidebar @select="selectSession" @create="onSessionCreated" />
    <section class="chat-page">
    <header class="chat-header">
      <div class="brand-mark">AI</div>
      <div>
        <h1>智能客服</h1>
        <p>随时为你解答问题</p>
      </div>
      <span v-if="sessionStore.currentSessionId != null" class="current-session">会话 #{{ sessionStore.currentSessionId }}</span>
      <el-button class="settings-link" text circle aria-label="偏好设置" title="偏好设置" @click="$router.push('/settings')">
        <el-icon><Setting /></el-icon>
      </el-button>
      <el-button class="settings-link" text circle aria-label="知识库" title="知识库" @click="$router.push('/knowledge')">
        <el-icon><Collection /></el-icon>
      </el-button>
    </header>

    <el-scrollbar ref="scrollbar" class="messages-scroll">
      <section v-if="!messages.length" class="welcome">
        <div class="welcome-icon">✦</div>
        <h2>你好，有什么可以帮你？</h2>
        <p>输入问题开始对话</p>
      </section>
      <div v-else class="message-list">
        <article v-for="item in messages" :key="item.id" class="message-row" :class="item.role">
          <div v-if="item.role === 'assistant'" class="avatar assistant-avatar">AI</div>
          <div class="message-column">
            <div class="bubble" :class="[`${item.role}-bubble`, { 'error-bubble': item.errorMessage }]">
              <span v-if="item.content" :class="{ 'error-text': item.errorMessage }">{{ item.errorMessage || item.content }}</span>
              <span v-else-if="sending && item === messages[messages.length - 1]" class="typing"><i></i><i></i><i></i></span>
            </div>
            <el-collapse v-if="item.role === 'assistant' && item.citations.length" v-model="item.citationsOpen" class="citations">
              <el-collapse-item title="参考来源" name="true">
                <div v-for="(citation, index) in item.citations" :key="index" class="citation-card">
                  <strong>{{ citation.doc_name || '参考文档' }}</strong>
                  <p>{{ citation.snippet || '暂无摘录内容' }}</p>
                </div>
              </el-collapse-item>
            </el-collapse>
            <div v-if="item.role === 'assistant' && typeof item.id === 'number' && !sending" class="message-feedback">
              <el-button text circle :disabled="item.feedbackSending || item.feedbackScore != null" aria-label="回答有帮助" title="有帮助" @click="sendFeedback(item, 1)">
                <el-icon :class="{ selected: item.feedbackScore === 1 }"><Like /></el-icon>
              </el-button>
              <el-button text circle :disabled="item.feedbackSending || item.feedbackScore != null" aria-label="回答没帮助" title="没帮助" @click="sendFeedback(item, -1)">
                <el-icon :class="{ selected: item.feedbackScore === -1 }"><Dislike /></el-icon>
              </el-button>
            </div>
          </div>
          <div v-if="item.role === 'user'" class="avatar user-avatar">我</div>
        </article>
        <div v-if="sending" class="stream-status"><span class="status-dot"></span>正在生成回复</div>
      </div>
    </el-scrollbar>

    <footer class="composer-wrap">
      <div class="composer">
        <el-input
          v-model="draft"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 5 }"
          resize="none"
          maxlength="4000"
          placeholder="输入你的问题…（Enter 发送，Shift + Enter 换行）"
          :disabled="sending"
          @keydown="onInputKeydown"
        />
        <el-button type="primary" :loading="sending" :disabled="!draft.trim() || sending" @click="sendMessage">
          {{ sending ? '发送中' : '发送' }}
        </el-button>
      </div>
      <p class="composer-hint">AI 生成的内容仅供参考</p>
    </footer>
    </section>
  </main>
</template>

<style scoped>
.chat-layout { width: min(100%, 1180px); height: 100dvh; margin: 0 auto; display: flex; background: #fff; color: #25334a; }.chat-page { width: min(100%, 860px); height: 100%; margin: 0 auto; display: flex; flex-direction: column; background: #fff; color: #25334a; }
.chat-header { height: 76px; flex: 0 0 76px; display: flex; align-items: center; gap: 12px; padding: 0 26px; border-bottom: 1px solid #edf0f5; }
.brand-mark { display: grid; place-items: center; width: 40px; height: 40px; border-radius: 14px; color: white; font-size: 13px; font-weight: 700; background: linear-gradient(135deg,#6aa7ff,#766cf5); }
.chat-header h1 { margin: 0; font-size: 16px; font-weight: 650; }.chat-header p { margin: 4px 0 0; color: #929bad; font-size: 12px; }.current-session { margin-left: auto; color: #9aa4b3; font-size: 12px; }.settings-link { margin-left: 6px; color: #8491a5; font-size: 18px; }.settings-link:hover { color: #5289df; background: #f0f5ff; }
.messages-scroll { flex: 1; min-height: 0; }.message-list { padding: 28px 28px 20px; }.message-row { display: flex; align-items: flex-start; gap: 10px; margin: 0 0 24px; }.message-row.user { justify-content: flex-end; }.message-column { max-width: min(76%, 650px); }.avatar { flex: 0 0 32px; width: 32px; height: 32px; display: grid; place-items: center; border-radius: 11px; font-size: 11px; font-weight: 700; }.assistant-avatar { background: #f0f2f7; color: #63718a; }.user-avatar { background: #eaf2ff; color: #4788e8; }
.bubble { padding: 12px 16px; border-radius: 16px; font-size: 14px; line-height: 1.75; white-space: pre-wrap; overflow-wrap: anywhere; }.assistant-bubble { background: #f3f5f8; color: #364257; border-top-left-radius: 5px; }.user-bubble { background: #e8f2ff; color: #24456e; border-top-right-radius: 5px; }.citations { margin-top: 8px; border: 1px solid #edf0f5; border-radius: 10px; overflow: hidden; }.citation-card { padding: 8px 10px; margin-bottom: 8px; border-radius: 8px; background: #f7f9fc; }.citation-card strong { color: #465875; font-size: 12px; }.citation-card p { margin: 5px 0 0; color: #78859a; font-size: 12px; line-height: 1.6; }.typing { display: inline-flex; gap: 4px; align-items: center; height: 18px; }.typing i { width: 6px; height: 6px; border-radius: 50%; background: #9aa6b8; animation: pulse 1s infinite ease-in-out; }.typing i:nth-child(2) { animation-delay: .15s; }.typing i:nth-child(3) { animation-delay: .3s; }@keyframes pulse { 50% { opacity: .3; transform: translateY(-3px); } }
.error-bubble { background: #fff5f5; }.error-text { color: #d94b4b; }
.message-feedback { display: flex; gap: 2px; margin-top: 5px; }.message-feedback :deep(.el-button) { width: 28px; height: 28px; margin: 0; color: #9aa5b5; }.message-feedback :deep(.el-button:hover) { color: #5289df; background: #f0f5ff; }.message-feedback .selected { color: #5289df; }
.stream-status { margin: -8px 0 10px 42px; color: #99a3b3; font-size: 12px; }.status-dot { display: inline-block; width: 6px; height: 6px; margin-right: 7px; border-radius: 50%; background: #72a9f8; animation: pulse 1s infinite; }.welcome { height: 100%; min-height: 360px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #9aa5b5; }.welcome-icon { display: grid; place-items: center; width: 54px; height: 54px; border-radius: 18px; background: #f1f5ff; color: #7699ed; font-size: 27px; }.welcome h2 { margin: 18px 0 6px; color: #43516a; font-size: 20px; font-weight: 600; }.welcome p { margin: 0; font-size: 13px; }
.composer-wrap { flex: 0 0 auto; padding: 14px 24px 10px; border-top: 1px solid #edf0f5; background: #fff; }.composer { display: flex; align-items: flex-end; gap: 12px; padding: 10px 10px 10px 14px; border: 1px solid #e5eaf1; border-radius: 16px; box-shadow: 0 5px 20px #344b6b0d; }.composer :deep(.el-textarea__inner) { padding: 7px 0; border: 0; box-shadow: none; font-size: 14px; line-height: 1.6; }.composer :deep(.el-textarea__inner:focus) { box-shadow: none; }.composer .el-button { height: 38px; padding: 0 19px; border-radius: 11px; }.composer-hint { margin: 8px 0 0; text-align: center; color: #a3adbb; font-size: 11px; }
@media (max-width: 700px) { :deep(.session-sidebar) { width: 68px; min-width: 68px; padding: 14px 8px; }.chat-layout :deep(.sidebar-brand span:last-child), .chat-layout :deep(.new-session), .chat-layout :deep(.section-label), .chat-layout :deep(.session-title), .chat-layout :deep(.sidebar-footer) { display: none; }.chat-layout :deep(.sidebar-brand) { justify-content: center; padding: 0 0 16px; }.chat-layout :deep(.session-item) { justify-content: center; padding: 0; }.chat-layout :deep(.delete-button) { display: none !important; }.chat-header { padding: 0 16px; }.message-list { padding: 20px 14px; }.message-column { max-width: 82%; }.composer-wrap { padding: 12px 12px 8px; }.welcome h2 { font-size: 18px; } }
</style>
