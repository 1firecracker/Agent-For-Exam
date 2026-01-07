<template>
  <div class="claude-layout" :style="{ '--sidebar-width': isCollapsed ? '48px' : '260px' }">
    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ collapsed: isCollapsed }">
      <div class="sidebar-header">
        <div class="logo-area" v-show="!isCollapsed">
          <h1 class="app-title">Agent Exam</h1>
        </div>
        <el-button class="new-chat-btn" @click="goHome" v-show="!isCollapsed">
          <el-icon></el-icon>
          HOME PAGE
        </el-button>
        <button class="collapse-btn" @click="toggleCollapse" :title="isCollapsed ? '展开侧边栏' : '折叠侧边栏'">
          <el-icon>
            <component :is="isCollapsed ? 'ArrowRight' : 'ArrowLeft'" />
          </el-icon>
        </button>
      </div>

      <nav class="sidebar-nav" v-show="!isCollapsed">
        <div class="nav-group">
          <router-link to="/" class="nav-item" active-class="active">
            <el-icon><Collection /></el-icon>
            My Projects
          </router-link>
        </div>
      </nav>

      <div class="sidebar-footer" v-show="!isCollapsed">
        <div class="user-profile" @click="$emit('open-settings')">
          <div class="avatar">U</div>
          <div class="info">
            <span class="name">User</span>
            <span class="status">Settings</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-content">
      <div class="content-wrapper">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>

    <!-- 全局插槽 (用于 SettingsDialog 等) -->
    <slot />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Collection, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'

const router = useRouter()
const isCollapsed = ref(false)

const goHome = () => {
  router.push('/')
}

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
}

// 动态设置全局CSS变量，供ChatView使用
watch(isCollapsed, (collapsed) => {
  document.documentElement.style.setProperty('--sidebar-width', collapsed ? '48px' : '260px')
}, { immediate: true })
</script>

<style scoped>
.claude-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  background-color: var(--bg-app);
  overflow: hidden;
}

/* Sidebar Styles */
.sidebar {
  width: 260px;
  background-color: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-subtle);
  flex-shrink: 0;
  transition: width 0.3s ease;
}

.sidebar.collapsed {
  width: 48px;
}

.sidebar-header {
  padding: 20px 16px;
  position: relative;
}

.collapse-btn {
  position: absolute;
  top: 20px;
  right: 16px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background-color: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  z-index: 10;
}

.collapse-btn:hover {
  background-color: rgba(0, 0, 0, 0.06);
  color: var(--text-primary);
}

.collapse-btn .el-icon {
  font-size: 16px;
}

.sidebar.collapsed .collapse-btn {
  right: 10px;
  top: 16px;
}

.app-title {
  font-family: var(--font-serif);
  font-size: 20px;
  color: var(--text-primary);
  margin-bottom: 16px;
  padding-left: 8px;
}

.new-chat-btn {
  width: 100%;
  height: 44px;
  background-color: var(--color-accent);
  border: none;
  border-radius: 8px;
  color: white;
  font-family: var(--font-sans);
  font-weight: 500;
  font-size: 14px;
  justify-content: flex-start;
  padding-left: 16px;
  transition: background-color 0.2s;
}

.new-chat-btn:hover {
  background-color: var(--color-accent-hover);
}

.new-chat-btn :deep(.el-icon) {
  margin-right: 8px;
  font-size: 18px;
}

/* Navigation */
.sidebar-nav {
  flex: 1;
  padding: 12px 16px;
  overflow-y: auto;
}

.nav-group {
  margin-bottom: 24px;
}

.group-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  margin-bottom: 8px;
  padding-left: 12px;
  letter-spacing: 0.05em;
}

.nav-item {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  transition: all 0.2s;
}

.nav-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
  color: var(--text-primary);
}

.nav-item.active {
  background-color: rgba(218, 119, 86, 0.1); /* Accent color with low opacity */
  color: var(--color-accent);
  font-weight: 500;
}

.nav-item .el-icon {
  margin-right: 10px;
  font-size: 18px;
}

/* Footer */
.sidebar-footer {
  padding: 16px;
  border-top: 1px solid var(--border-subtle);
}

.user-profile {
  display: flex;
  align-items: center;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.user-profile:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.avatar {
  width: 32px;
  height: 32px;
  background-color: #E0DDD6;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-serif);
  font-weight: 700;
  color: var(--text-secondary);
  margin-right: 10px;
}

.info {
  display: flex;
  flex-direction: column;
}

.name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.status {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* Main Content */
.main-content {
  flex: 1;
  overflow-y: auto;
  position: relative;
}

.content-wrapper {
  max-width: 1000px; /* Claude style limitation */
  margin: 0 auto;
  padding: 40px;
  min-height: 100%;
}

/* Transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
