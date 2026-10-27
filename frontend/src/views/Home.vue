<script setup lang="ts">
import { onMounted } from "vue";

import { useHealthStore } from "@/stores/health";

const healthStore = useHealthStore();

onMounted(() => {
  void healthStore.fetchHealth();
});
</script>

<template>
  <el-container class="home">
    <el-main>
      <el-card>
        <template #header>健康检查</template>
        <el-text v-if="healthStore.loading">正在请求 /api/health ...</el-text>
        <el-alert
          v-else-if="healthStore.error"
          :title="healthStore.error"
          type="error"
          show-icon
          :closable="false"
        />
        <pre v-else>{{ healthStore.result }}</pre>
      </el-card>
    </el-main>
  </el-container>
</template>

<style scoped>
.home {
  max-width: 640px;
  margin: 48px auto;
}
</style>
