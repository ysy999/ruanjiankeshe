import { createRouter, createWebHistory } from "vue-router";

import Home from "@/views/Home.vue";
import ChatView from "@/views/ChatView.vue";
import SettingsView from "@/views/SettingsView.vue";
import KnowledgeView from "@/views/KnowledgeView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: Home,
    },
    {
      path: "/chat",
      name: "chat",
      component: ChatView,
    },
    {
      path: "/settings",
      name: "settings",
      component: SettingsView,
    },
    {
      path: "/knowledge",
      name: "knowledge",
      component: KnowledgeView,
    },
  ],
});

export default router;
