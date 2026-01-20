import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import SubjectDocsView from '../views/SubjectDocsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView
    },
    {
      path: '/subject/:id',
      name: 'subject-docs',
      component: SubjectDocsView
    },
    {
      path: '/subject/:subjectId/chat/:conversationId',
      name: 'chat',
      component: () => import('../modules/chat/ChatView.vue')
    },
    {
      path: '/chat/:id',
      name: 'chat-legacy',
      component: () => import('../modules/chat/ChatView.vue')
    }
  ]
})

export default router
