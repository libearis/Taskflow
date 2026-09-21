import { createRouter, createWebHistory } from "vue-router";

import BoardView from "./views/BoardView.vue";
import DashboardView from "./views/DashboardView.vue";
import ProjectListView from "./views/ProjectListView.vue";

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "projects", component: ProjectListView },
    { path: "/projects/:projectId/board", name: "board", component: BoardView, props: true },
    { path: "/users/:userId/workload", name: "dashboard", component: DashboardView, props: true },
  ],
});
