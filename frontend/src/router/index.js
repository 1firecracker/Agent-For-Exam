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
      path: '/chat/:id',
      name: 'chat',
      component: () => import('../modules/chat/ChatView.vue')
    },
    
  ]
})

export default router
