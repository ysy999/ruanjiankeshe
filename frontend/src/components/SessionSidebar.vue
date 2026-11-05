<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { useSessionStore, type SessionItem } from "@/stores/sessions";

const store = useSessionStore();
const emit = defineEmits<{
  select: [session: SessionItem];
  create: [];
}>();

function select(session: SessionItem) {
  store.setCurrentSession(session.id);
  emit("select", session);
}

async function createSession() {
  try {
    const session = await store.createSession();
    emit("create");
    // Parent loads the new session's (empty) history via the same selection path.
    emit("select", session);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "创建会话失败");
  }
}

async function deleteSession(session: SessionItem) {
  try {
    await ElMessageBox.confirm(`确定删除“${session.title || "新对话"}”吗？`, "删除会话", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    });
    await store.deleteSession(session.id);
    ElMessage.success("会话已删除");
    if (store.currentSessionId == null && store.sessions.length) select(store.sessions[0]!);
  } catch (error) {
    if (error !== "cancel" && error !== "close") {
      ElMessage.error(error instanceof Error ? error.message : "删除会话失败");
    }
  }
}
</script>

<template>
  <aside class="session-sidebar">
    <div class="sidebar-top">
      <div class="sidebar-brand"><span class="brand-icon">AI</span><span>智能客服</span></div>
      <el-button class="new-session" plain @click="createSession">
        <el-icon><Plus /></el-icon>新建会话
      </el-button>
      <div class="section-label">最近对话</div>
    </div>
    <el-scrollbar class="session-scroll">
      <div v-if="store.loading && !store.sessions.length" class="empty-state">正在加载…</div>
      <div v-else-if="!store.sessions.length" class="empty-state">暂无会话</div>
      <div
        v-for="session in store.sessions"
        :key="session.id"
        class="session-item"
        :class="{ active: String(store.currentSessionId) === String(session.id) }"
        @click="select(session)"
      >
        <el-icon class="conversation-icon"><ChatDotRound /></el-icon>
        <span class="session-title">{{ session.title || '新对话' }}</span>
        <el-button class="delete-button" text circle aria-label="删除会话" @click.stop="deleteSession(session)">
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </el-scrollbar>
    <div class="sidebar-footer"><span class="online-dot"></span>服务已就绪</div>
  </aside>
</template>

<style scoped>
.session-sidebar { width: 258px; min-width: 258px; height: 100%; display: flex; flex-direction: column; padding: 20px 14px 12px; box-sizing: border-box; background: #f7f8fb; border-right: 1px solid #edf0f5; color: #364257; }
.sidebar-top { flex: 0 0 auto; }.sidebar-brand { display: flex; align-items: center; gap: 10px; padding: 0 7px 23px; font-size: 15px; font-weight: 650; }.brand-icon { display: grid; place-items: center; width: 32px; height: 32px; border-radius: 11px; background: linear-gradient(135deg,#6aa7ff,#766cf5); color: #fff; font-size: 10px; }.new-session { width: 100%; height: 39px; justify-content: flex-start; border-radius: 10px; border-color: #e4e9f1; background: #fff; color: #4c6fa5; font-weight: 550; }.section-label { padding: 23px 8px 9px; color: #9aa4b3; font-size: 11px; letter-spacing: .04em; }.session-scroll { flex: 1; min-height: 0; }.session-item { display: flex; align-items: center; gap: 9px; min-height: 40px; margin: 2px 0; padding: 0 8px; border-radius: 9px; cursor: pointer; color: #69768b; transition: background .15s,color .15s; }.session-item:hover { background: #eef1f6; }.session-item.active { background: #e9f1ff; color: #397ad3; }.conversation-icon { flex: 0 0 auto; font-size: 15px; }.session-title { overflow: hidden; flex: 1; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }.delete-button { display: none; width: 26px; height: 26px; color: #929bad; }.session-item:hover .delete-button { display: inline-flex; }.delete-button:hover { color: #e56c6c; background: #fff; }.empty-state { padding: 12px 8px; color: #a1aaba; font-size: 12px; }.sidebar-footer { display: flex; align-items: center; gap: 7px; padding: 14px 7px 2px; color: #9ba5b4; font-size: 11px; }.online-dot { width: 7px; height: 7px; border-radius: 50%; background: #65c99b; }
</style>
