<template>
  <el-container class="app-container">
    <el-header>
      <h1>Agent for Exam</h1>
      <div class="header-right">
        <el-button 
          :icon="Setting" 
          circle 
          @click="showSettings = true"
          title="设置"
        />
      </div>
    </el-header>
    <el-main>
      <router-view />
    </el-main>
    
    <!-- 设置对话框 -->
    <SettingsDialog v-model="showSettings" />
  </el-container>
</template>

<script setup>
import { ref } from 'vue'
import { Setting } from '@element-plus/icons-vue'
import SettingsDialog from './components/SettingsDialog.vue'

const showSettings = ref(false)
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
}

#app {
  width: 100%;
  height: 100vh;
}

.app-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.el-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #409eff;
  color: white;
  padding: 0 20px;
  height: 60px !important; /* 固定 header 高度 */
  flex-shrink: 0;
}

.el-header h1 {
  font-size: 20px;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.el-main {
  padding: 0;
  height: calc(100vh - 60px); /* 减去 header 高度 */
  overflow: hidden;
  flex: 1; /* 填充剩余空间 */
}
</style>
