import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import DocumentView from '../views/DocumentView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'document',
      component: DocumentView
    },
    {
      path: '/test',
      name: 'home',
      component: HomeView
    }
  ]
})

export default router
