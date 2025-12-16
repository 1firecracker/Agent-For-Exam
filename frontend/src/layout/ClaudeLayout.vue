<template>
  <div class="claude-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="logo-area">
          <h1 class="app-title">Agent Exam</h1>
        </div>
        <el-button class="new-chat-btn" @click="goHome">
          <el-icon></el-icon>
          HOME PAGE
        </el-button>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-group">
          <router-link to="/" class="nav-item" active-class="active">
            <el-icon><Collection /></el-icon>
            My Projects
          </router-link>
        </div>

        <div class="nav-group">
           <div class="group-title">Tools</div>
           <router-link to="/exam" class="nav-item" active-class="active">
            <el-icon><EditPen /></el-icon>
            Exam Generator
          </router-link>
           <router-link to="/grading" class="nav-item" active-class="active">
            <el-icon><Check /></el-icon>
            Smart Grading
          </router-link>
        </div>
      </nav>

      <div class="sidebar-footer">
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
import { useRouter } from 'vue-router'
import { Plus, Collection, EditPen, Check } from '@element-plus/icons-vue'

const router = useRouter()

const goHome = () => {
  router.push('/')
}
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
}

.sidebar-header {
  padding: 20px 16px;
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
