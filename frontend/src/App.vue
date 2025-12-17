<template>
  <ClaudeLayout @open-settings="showSettings = true">
    <!-- 设置对话框 -->
    <SettingsDialog v-model="showSettings" />
  </ClaudeLayout>
</template>

<script setup>
import { ref } from 'vue'
import SettingsDialog from './components/SettingsDialog.vue'
import ClaudeLayout from './layout/ClaudeLayout.vue'

const showSettings = ref(false)
</script>

<style>
/* 全局重置已经在 theme.css 中处理 */
#app {
  width: 100%;
  height: 100vh;
}
</style>
