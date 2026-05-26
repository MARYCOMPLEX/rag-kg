import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '../app/AppShell.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: AppShell,
      children: [
        { path: '', redirect: '/libraries/graphrag-survey/chat' },
        {
          path: 'libraries',
          name: 'libraries',
          component: () => import('../views/LibraryDashboardView.vue'),
          meta: { shell: 'overview', hideSidebar: true, section: 'Libraries' },
        },
        {
          path: 'libraries/:libraryId/chat',
          name: 'library-chat',
          component: () => import('../views/ChatView.vue'),
          meta: { shell: 'workspace', section: 'Chat' },
        },
        {
          path: 'libraries/:libraryId/kg',
          name: 'library-graph',
          component: () => import('../views/GraphView.vue'),
          meta: { shell: 'workspace', section: 'Knowledge Graph' },
        },
        {
          path: 'libraries/:libraryId/docs',
          name: 'library-docs',
          component: () => import('../views/DocumentsView.vue'),
          meta: { shell: 'workspace', section: 'Documents' },
        },
        {
          path: 'libraries/:libraryId/review',
          name: 'library-review',
          component: () => import('../views/ReviewView.vue'),
          meta: { shell: 'workspace', section: 'Review' },
        },
        {
          path: 'libraries/:libraryId/eval',
          name: 'library-eval',
          component: () => import('../views/EvaluationView.vue'),
          meta: { shell: 'workspace', section: 'Evaluation' },
        },
      ],
    },
  ],
})
