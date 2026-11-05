<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox, type UploadFile, type UploadProps } from "element-plus";
import { apiFetch } from "@/api/client";

type KnowledgeDocument = {
  id: number | string;
  filename: string;
  doc_type: string;
  chunk_count: number;
  version: string | number;
  updated_at: string;
  status: string;
};

const documents = ref<KnowledgeDocument[]>([]);
const loading = ref(false);
const uploading = ref(false);
const feedbackVisible = ref(false);
const feedbackLoading = ref(false);
const feedbacks = ref<Array<{ id: number; session_id: number; message_id: number; score: number; comment?: string; message_content?: string; created_at: string }>>([]);
const metricsLoading = ref(false);
const metrics = ref({ avg_total_ms: 0, avg_retrieve_ms: 0, success_rate: 0, sample_count: 0 });
const allowedExtensions = new Set(["md", "pdf", "txt"]);

function unwrap<T>(payload: unknown): T {
  if (payload && typeof payload === "object" && "data" in payload) {
    return (payload as { data: T }).data;
  }
  return payload as T;
}

async function refreshDocuments() {
  loading.value = true;
  try {
    const response = await apiFetch("/api/knowledge");
    if (!response.ok) throw new Error(`加载失败（HTTP ${response.status}）`);
    const result = unwrap<KnowledgeDocument[] | { documents: KnowledgeDocument[] }>(await response.json());
    documents.value = Array.isArray(result) ? result : result.documents;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载知识库失败");
  } finally {
    loading.value = false;
  }
}

async function openFeedback() {
  feedbackVisible.value = true;
  feedbackLoading.value = true;
  try {
    const response = await apiFetch("/api/feedback/pending");
    if (!response.ok) throw new Error(`加载反馈失败（HTTP ${response.status}）`);
    const result = unwrap<typeof feedbacks.value | { feedbacks: typeof feedbacks.value }>(await response.json());
    feedbacks.value = Array.isArray(result) ? result : result.feedbacks;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载反馈失败");
  } finally {
    feedbackLoading.value = false;
  }
}

async function refreshMetrics() {
  metricsLoading.value = true;
  try {
    const response = await apiFetch("/api/metrics");
    if (!response.ok) throw new Error(`加载指标失败（HTTP ${response.status}）`);
    const result = unwrap<typeof metrics.value>(await response.json());
    metrics.value = { ...metrics.value, ...result };
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载运行指标失败");
  } finally {
    metricsLoading.value = false;
  }
}

const beforeUpload: UploadProps["beforeUpload"] = (file) => {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!allowedExtensions.has(extension)) {
    ElMessage.warning("仅支持上传 .md、.pdf、.txt 文件");
    return false;
  }
  uploading.value = true;
  return true;
};

const onUploadSuccess: UploadProps["onSuccess"] = async () => {
  uploading.value = false;
  ElMessage.success("文件上传成功");
  await refreshDocuments();
};

const onUploadError: UploadProps["onError"] = (error) => {
  uploading.value = false;
  ElMessage.error(error.message || "文件上传失败");
};

const onUploadChange: UploadProps["onChange"] = (uploadFile: UploadFile) => {
  if (uploadFile.status === "ready") uploading.value = true;
};

async function reindex(document: KnowledgeDocument) {
  try {
    const response = await apiFetch(`/api/knowledge/${encodeURIComponent(document.id)}/reindex`, { method: "POST" });
    if (!response.ok) throw new Error(`重新索引失败（HTTP ${response.status}）`);
    ElMessage.success("已提交重新索引");
    await refreshDocuments();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "重新索引失败");
  }
}

async function removeDocument(document: KnowledgeDocument) {
  try {
    await ElMessageBox.confirm(`确定删除“${document.filename}”吗？`, "删除文档", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    });
    const response = await apiFetch(`/api/knowledge/${encodeURIComponent(document.id)}`, { method: "DELETE" });
    if (!response.ok) throw new Error(`删除失败（HTTP ${response.status}）`);
    ElMessage.success("文档已删除");
    await refreshDocuments();
  } catch (error) {
    if (error !== "cancel" && error !== "close") {
      ElMessage.error(error instanceof Error ? error.message : "删除文档失败");
    }
  }
}

function statusType(status: string): "success" | "primary" | "danger" | "info" | "warning" {
  const normalized = status.toLowerCase();
  if (["已索引", "indexed", "success", "completed"].includes(normalized)) return "success";
  if (["更新中", "处理中", "updating", "processing", "pending"].includes(normalized)) return "primary";
  if (["失败", "failed", "error"].includes(normalized)) return "danger";
  return "info";
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    indexed: "已索引", success: "已索引", completed: "已索引",
    updating: "更新中", processing: "更新中", pending: "更新中",
    failed: "失败", error: "失败",
  };
  return labels[status.toLowerCase()] ?? status;
}

onMounted(() => {
  void refreshDocuments();
  void refreshMetrics();
});
</script>

<template>
  <main class="knowledge-page">
    <header class="page-header">
      <div>
        <div class="eyebrow">KNOWLEDGE BASE</div>
        <h1>知识库</h1>
        <p>管理客服 AI 用于回答问题的参考文档。</p>
      </div>
      <el-button text class="back-link" @click="$router.push('/chat')">
        <el-icon><ArrowLeft /></el-icon>返回对话
      </el-button>
      <el-button class="feedback-button" @click="openFeedback"><el-icon><ChatLineSquare /></el-icon>用户反馈</el-button>
    </header>

    <el-upload
      class="upload-area"
      drag
      action="/api/knowledge/upload"
      accept=".md,.pdf,.txt"
      :before-upload="beforeUpload"
      :on-success="onUploadSuccess"
      :on-error="onUploadError"
      :on-change="onUploadChange"
      :show-file-list="false"
      :disabled="uploading"
    >
      <el-icon class="upload-icon"><UploadFilled /></el-icon>
      <div class="upload-title">拖拽文件到此处，或 <em>点击上传</em></div>
      <div class="upload-hint">支持 Markdown、PDF、TXT，单次可上传多个文件</div>
      <div v-if="uploading" class="upload-progress">文件处理中…</div>
    </el-upload>

    <section v-loading="metricsLoading" class="metrics-card">
      <div class="metrics-title"><div><h2>问答运行指标</h2><span>最近 {{ metrics.sample_count }} 次</span></div><el-button text @click="refreshMetrics"><el-icon><Refresh /></el-icon></el-button></div>
      <div class="metrics-grid">
        <div><span>平均总耗时</span><strong>{{ metrics.avg_total_ms }}<small> ms</small></strong></div>
        <div><span>平均检索耗时</span><strong>{{ metrics.avg_retrieve_ms }}<small> ms</small></strong></div>
        <div><span>成功率</span><strong>{{ (metrics.success_rate * 100).toFixed(1) }}<small>%</small></strong></div>
      </div>
    </section>

    <section class="documents-section">
      <div class="section-heading">
        <div><h2>文档列表</h2><span>{{ documents.length }} 个文档</span></div>
        <el-button :loading="loading" text @click="refreshDocuments">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
      </div>
      <el-table v-loading="loading" :data="documents" row-key="id" class="documents-table" empty-text="暂无文档，上传文件开始构建知识库">
        <el-table-column prop="filename" label="文件名" min-width="190" show-overflow-tooltip />
        <el-table-column prop="doc_type" label="类型" width="95" />
        <el-table-column prop="chunk_count" label="分块数" width="90" />
        <el-table-column prop="version" label="版本" width="75" />
        <el-table-column prop="updated_at" label="更新时间" min-width="155" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" effect="light" round>{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="155" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="reindex(row)">重新索引</el-button>
            <el-button link type="danger" @click="removeDocument(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-drawer v-model="feedbackVisible" title="待复审用户反馈" size="min(620px, 92vw)">
      <div v-loading="feedbackLoading" class="feedback-list">
        <el-empty v-if="!feedbackLoading && !feedbacks.length" description="暂无待复审反馈" />
        <el-card v-for="feedback in feedbacks" :key="feedback.id" shadow="never" class="feedback-card">
          <div class="feedback-card-top">
            <el-tag :type="feedback.score > 0 ? 'success' : 'danger'" effect="light">
              {{ feedback.score > 0 ? '👍 有帮助' : '👎 没帮助' }}
            </el-tag>
            <span>{{ feedback.created_at }}</span>
          </div>
          <p class="feedback-answer">{{ feedback.message_content || '回答内容不可用' }}</p>
          <p v-if="feedback.comment" class="feedback-comment">反馈：{{ feedback.comment }}</p>
          <div class="feedback-meta">会话 #{{ feedback.session_id }} · 消息 #{{ feedback.message_id }}</div>
        </el-card>
      </div>
    </el-drawer>
  </main>
</template>

<style scoped>
.knowledge-page { width: min(100% - 40px, 1120px); min-height: 100dvh; margin: 0 auto; padding: 42px 0 56px; color: #29364c; box-sizing: border-box; }.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 25px; }.eyebrow { margin-bottom: 8px; color: #7d9bd0; font-size: 10px; font-weight: 700; letter-spacing: .13em; }.page-header h1 { margin: 0; font-size: 27px; font-weight: 650; }.page-header p { margin: 8px 0 0; color: #8d98aa; font-size: 13px; }.back-link { margin-top: 6px; color: #748199; }
.feedback-button { margin-left: auto; margin-right: 12px; border-radius: 9px; }.feedback-list { display: grid; gap: 12px; }.feedback-card { border-color: #edf0f5; border-radius: 12px; }.feedback-card-top { display: flex; align-items: center; justify-content: space-between; color: #9aa4b3; font-size: 11px; }.feedback-answer { margin: 14px 0 8px; color: #46536a; font-size: 13px; line-height: 1.65; }.feedback-comment { padding: 10px 12px; border-radius: 8px; background: #f7f8fb; color: #6e7c91; font-size: 12px; }.feedback-meta { color: #a3adbb; font-size: 10px; }
.metrics-card { margin-top: 19px; padding: 17px 20px 19px; border: 1px solid #edf0f5; border-radius: 14px; background: linear-gradient(120deg,#fff,#f9fbff); }.metrics-title { display: flex; align-items: center; justify-content: space-between; }.metrics-title > div { display: flex; align-items: baseline; gap: 10px; }.metrics-title h2 { margin: 0; font-size: 14px; font-weight: 620; }.metrics-title span { color: #a1aaba; font-size: 10px; }.metrics-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 15px; margin-top: 17px; }.metrics-grid > div { display: flex; flex-direction: column; gap: 8px; }.metrics-grid span { color: #8793a7; font-size: 11px; }.metrics-grid strong { color: #3e5e8c; font-size: 21px; font-weight: 650; }.metrics-grid small { color: #9aa5b5; font-size: 11px; font-weight: 450; }
.upload-area { width: 100%; }.upload-area :deep(.el-upload) { width: 100%; }.upload-area :deep(.el-upload-dragger) { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; min-height: 174px; padding: 24px 16px; box-sizing: border-box; border: 1px dashed #cbd8ea; border-radius: 15px; background: #fbfcff; transition: border-color .2s,background .2s; }.upload-area :deep(.el-upload-dragger:hover) { border-color: #75a3ed; background: #f7faff; }.upload-icon { margin-bottom: 12px; color: #7fa5e5; font-size: 28px; }.upload-title { color: #586780; font-size: 14px; }.upload-title em { color: #5088de; font-style: normal; }.upload-hint { margin-top: 8px; color: #a1aaba; font-size: 11px; }.upload-progress { margin-top: 10px; color: #5289df; font-size: 12px; }
.documents-section { margin-top: 35px; }.section-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }.section-heading > div { display: flex; align-items: baseline; gap: 10px; }.section-heading h2 { margin: 0; font-size: 16px; font-weight: 620; }.section-heading span { color: #a1aaba; font-size: 11px; }.documents-table { width: 100%; border: 1px solid #edf0f5; border-radius: 12px; overflow: hidden; }.documents-table :deep(th.el-table__cell) { background: #f8f9fb; color: #78859a; font-size: 11px; font-weight: 600; }.documents-table :deep(td.el-table__cell) { color: #49566c; font-size: 12px; }.documents-table :deep(.el-tag) { border: 0; }
@media (max-width: 700px) { .knowledge-page { width: min(100% - 24px, 1120px); padding-top: 25px; }.page-header h1 { font-size: 23px; }.upload-area :deep(.el-upload-dragger) { min-height: 150px; }.documents-section { margin-top: 27px; }.documents-table { overflow-x: auto; } }
</style>
