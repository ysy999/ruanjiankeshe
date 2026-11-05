import { defineStore } from "pinia";
import { ref } from "vue";
import { apiFetch } from "@/api/client";

export type SessionItem = {
  id: number | string;
  title?: string;
  created_at?: string;
  updated_at?: string;
};

export type HistoryMessage = {
  id: number | string;
  role: "user" | "assistant" | "system";
  content: string;
  citations?: Array<{ doc_name?: string; snippet?: string }> | null;
};

function unwrap<T>(payload: unknown): T {
  if (payload && typeof payload === "object" && "data" in payload) {
    return (payload as { data: T }).data;
  }
  return payload as T;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(url, init);
  if (!response.ok) throw new Error(`请求失败（HTTP ${response.status}）`);
  if (response.status === 204) return undefined as T;
  return unwrap<T>(await response.json());
}

export const useSessionStore = defineStore("sessions", () => {
  const sessions = ref<SessionItem[]>([]);
  const currentSessionId = ref<number | string | null>(null);
  const loading = ref(false);

  async function fetchSessions() {
    loading.value = true;
    try {
      const result = await request<SessionItem[] | { sessions: SessionItem[] }>("/api/sessions");
      sessions.value = Array.isArray(result) ? result : result.sessions;
      if (currentSessionId.value != null && !sessions.value.some((item) => String(item.id) === String(currentSessionId.value))) {
        currentSessionId.value = null;
      }
    } finally {
      loading.value = false;
    }
  }

  async function createSession() {
    const result = await request<SessionItem | { session: SessionItem }>("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "新对话" }),
    });
    const session = "session" in result ? result.session : result;
    sessions.value.unshift(session);
    currentSessionId.value = session.id;
    return session;
  }

  async function fetchMessages(id: number | string) {
    const result = await request<HistoryMessage[] | { messages: HistoryMessage[] }>(`/api/sessions/${encodeURIComponent(id)}/messages`);
    return Array.isArray(result) ? result : result.messages;
  }

  async function deleteSession(id: number | string) {
    await request<void>(`/api/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });
    sessions.value = sessions.value.filter((item) => String(item.id) !== String(id));
    if (String(currentSessionId.value) === String(id)) currentSessionId.value = null;
  }

  function setCurrentSession(id: number | string | null) {
    currentSessionId.value = id;
  }

  return { sessions, currentSessionId, loading, fetchSessions, createSession, fetchMessages, deleteSession, setCurrentSession };
});
