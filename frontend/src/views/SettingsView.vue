<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { apiFetch } from "@/api/client";

type Profile = {
  style: "formal" | "friendly" | "concise";
  length: "short" | "medium" | "long";
  showSources: boolean;
  nickname: string;
};

const profile = reactive<Profile>({ style: "friendly", length: "medium", showSources: true, nickname: "" });
const loading = ref(false);
const saving = ref(false);

function applyProfile(data: Partial<Profile> | { data?: Partial<Profile> }) {
  const wrapped = data as { data?: Partial<Profile> };
  const value: Partial<Profile> = wrapped.data ?? data as Partial<Profile>;
  if (value.style) profile.style = value.style;
  if (value.length) profile.length = value.length;
  if (typeof value.showSources === "boolean") profile.showSources = value.showSources;
  if (typeof value.nickname === "string") profile.nickname = value.nickname;
}

async function loadProfile() {
  loading.value = true;
  try {
    const response = await apiFetch("/api/profile");
    if (!response.ok) throw new Error(`加载失败（HTTP ${response.status}）`);
    applyProfile(await response.json() as Partial<Profile> | { data?: Partial<Profile> });
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载偏好设置失败");
  } finally {
    loading.value = false;
  }
}

async function saveProfile() {
  saving.value = true;
  try {
    const response = await apiFetch("/api/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });
    if (!response.ok) throw new Error(`保存失败（HTTP ${response.status}）`);
    ElMessage.success("偏好设置已保存");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存偏好设置失败");
  } finally {
    saving.value = false;
  }
}

onMounted(() => void loadProfile());
</script>

<template>
  <main class="settings-page" v-loading="loading">
    <header class="settings-header">
      <el-button class="back-button" text @click="$router.push('/chat')">
        <el-icon><ArrowLeft /></el-icon>返回对话
      </el-button>
      <div class="heading-icon"><el-icon><Setting /></el-icon></div>
      <h1>偏好设置</h1>
      <p>自定义 AI 回复方式，让对话更符合你的习惯。</p>
    </header>

    <el-card class="settings-card" shadow="never">
      <el-form label-position="top" :model="profile" class="settings-form">
        <el-form-item label="回复风格">
          <el-radio-group v-model="profile.style" class="choice-group">
            <el-radio-button value="formal">正式</el-radio-button>
            <el-radio-button value="friendly">友好</el-radio-button>
            <el-radio-button value="concise">简洁</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="回复长度">
          <el-radio-group v-model="profile.length" class="choice-group">
            <el-radio-button value="short">简短</el-radio-button>
            <el-radio-button value="medium">适中</el-radio-button>
            <el-radio-button value="long">详细</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="显示参考来源">
          <div class="switch-row">
            <span class="field-hint">在回答下方展示引用的文档和内容</span>
            <el-switch v-model="profile.showSources" />
          </div>
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="profile.nickname" maxlength="40" placeholder="希望 AI 如何称呼你" clearable />
        </el-form-item>
        <div class="form-actions">
          <el-button type="primary" :loading="saving" @click="saveProfile">保存设置</el-button>
        </div>
      </el-form>
    </el-card>
    <p class="settings-footnote">偏好设置将应用于后续对话</p>
  </main>
</template>

<style scoped>
.settings-page { width: min(100% - 32px, 600px); min-height: 100dvh; margin: 0 auto; padding: 22px 0 40px; box-sizing: border-box; color: #29364c; }
.settings-header { position: relative; padding: 25px 8px 24px; text-align: center; }.back-button { position: absolute; top: 0; left: 0; color: #718099; }.heading-icon { display: grid; place-items: center; width: 48px; height: 48px; margin: 0 auto 13px; border-radius: 15px; background: #edf3ff; color: #648fe0; font-size: 22px; }.settings-header h1 { margin: 0; font-size: 23px; font-weight: 650; }.settings-header p { margin: 8px 0 0; color: #8d98aa; font-size: 13px; }
.settings-card { border: 1px solid #edf0f5; border-radius: 16px; }.settings-form { padding: 6px 8px; }.settings-form :deep(.el-form-item) { margin-bottom: 25px; }.settings-form :deep(.el-form-item__label) { padding-bottom: 10px; color: #46536a; font-size: 13px; font-weight: 600; }.choice-group { display: flex; width: 100%; }.choice-group :deep(.el-radio-button) { flex: 1; }.choice-group :deep(.el-radio-button__inner) { width: 100%; padding: 10px 12px; }.switch-row { display: flex; align-items: center; justify-content: space-between; width: 100%; }.field-hint { color: #929daf; font-size: 12px; }.form-actions { display: flex; justify-content: flex-end; padding-top: 3px; }.form-actions .el-button { min-width: 112px; height: 39px; border-radius: 10px; }.settings-footnote { margin: 15px 0 0; text-align: center; color: #a6afbd; font-size: 11px; }
@media (max-width: 480px) { .settings-page { width: min(100% - 24px, 600px); padding-top: 14px; }.settings-header { padding-top: 34px; }.settings-header h1 { font-size: 21px; }.settings-form { padding: 4px 2px; }.choice-group :deep(.el-radio-button__inner) { padding: 10px 6px; } }
</style>
