import { defineStore } from "pinia";
import { ref } from "vue";

type HealthResponse = {
  status: string;
};

export const useHealthStore = defineStore("health", () => {
  const result = ref("");
  const loading = ref(false);
  const error = ref("");

  async function fetchHealth() {
    loading.value = true;
    error.value = "";
    try {
      const response = await fetch("/api/health");
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = (await response.json()) as HealthResponse;
      result.value = JSON.stringify(data);
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err);
      result.value = "";
    } finally {
      loading.value = false;
    }
  }

  return { result, loading, error, fetchHealth };
});
