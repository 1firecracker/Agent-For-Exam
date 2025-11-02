<template>
  <div class="document-view">
    <!-- 左侧栏（15%宽度，可折叠） -->
    <el-aside 
      :width="sidebarCollapsed ? '60px' : '15%'"
      class="sidebar-container"
    >
      <div class="sidebar-header">
        <el-button
          text
          :icon="sidebarCollapsed ? Expand : Fold"
          @click="toggleSidebar"
          class="collapse-btn"
        />
      </div>
      
      <ConversationSidebar 
        v-if="!sidebarCollapsed" 
        @document-select="handleDocumentSelect"
      />
      
      <!-- 折叠后的图标栏 -->
      <div v-else class="icon-bar">
        <el-tooltip content="对话管理" placement="right">
          <el-button text :icon="ChatLineRound" @click="toggleSidebar" />
        </el-tooltip>
        <el-tooltip content="文档管理" placement="right">
          <el-button text :icon="Document" @click="toggleSidebar" />
        </el-tooltip>
      </div>
    </el-aside>
    
    <!-- 中间对话区域（可调整大小） -->
    <div 
      class="chat-container" 
      :style="{ width: chatWidth + '%', minWidth: '300px', maxWidth: '80%' }"
    >
      <ChatPanel />
    </div>
    
    <!-- 可拖动分隔条 -->
    <div 
      class="resizer"
      @mousedown="handleResizeStart"
    >
      <div class="resizer-handle"></div>
    </div>
    
    <!-- 右侧视图区域（自动填充剩余空间，PPT/图谱切换） -->
    <div 
      class="view-container" 
      style="min-width: 300px;"
    >
      <ViewSwitcher :current-document-id="currentDocumentId" />
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import { Fold, Expand, ChatLineRound, Document } from '@element-plus/icons-vue'
import ConversationSidebar from '../components/DocumentView/ConversationSidebar.vue'
import ChatPanel from '../components/DocumentView/ChatPanel.vue'
import ViewSwitcher from '../components/DocumentView/ViewSwitcher.vue'

// 侧边栏折叠状态（默认展开）
const sidebarCollapsed = ref(false)

// 当前选中的文档ID
const currentDocumentId = ref(null)

// 区域宽度（初始值：对话40%，视图45%，分隔条固定5px）
const chatWidth = ref(40)
const isResizing = ref(false)
const resizeStartX = ref(0)
const resizeStartChatWidth = ref(40)

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

// 处理文档选择
const handleDocumentSelect = (fileId) => {
  currentDocumentId.value = fileId
}

// 开始调整大小
const handleResizeStart = (e) => {
  isResizing.value = true
  resizeStartX.value = e.clientX
  resizeStartChatWidth.value = chatWidth.value
  
  // 防止文本选择
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'col-resize'
  
  // 添加全局事件监听
  document.addEventListener('mousemove', handleResize)
  document.addEventListener('mouseup', handleResizeEnd)
  
  e.preventDefault()
}

// 调整大小中
const handleResize = (e) => {
  if (!isResizing.value) return
  
  const deltaX = e.clientX - resizeStartX.value
  const deltaPercent = (deltaX / window.innerWidth) * 100
  
  // 计算新的对话区域宽度
  let newChatWidth = resizeStartChatWidth.value + deltaPercent
  
  // 限制最小和最大宽度
  const minChatWidth = 300 // 最小300px
  const maxChatWidth = window.innerWidth * 0.8 // 最大80%宽度
  const minChatWidthPercent = (minChatWidth / window.innerWidth) * 100
  const maxChatWidthPercent = 80
  
  newChatWidth = Math.max(minChatWidthPercent, Math.min(maxChatWidthPercent, newChatWidth))
  
  chatWidth.value = newChatWidth
}

// 结束调整大小
const handleResizeEnd = () => {
  if (isResizing.value) {
    isResizing.value = false
    document.body.style.userSelect = ''
    document.body.style.cursor = ''
    
    // 移除全局事件监听
    document.removeEventListener('mousemove', handleResize)
    document.removeEventListener('mouseup', handleResizeEnd)
  }
}

// 组件卸载时清理
onUnmounted(() => {
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', handleResizeEnd)
})
</script>

<style scoped>
.document-view {
  display: flex;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.sidebar-container {
  height: 100%;
  background-color: #f5f5f5;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  overflow: hidden;
}

.sidebar-header {
  padding: 12px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: flex-end;
  background-color: #fff;
}

.collapse-btn {
  padding: 4px;
}

.icon-bar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 12px 4px;
}

.icon-bar .el-button {
  width: 40px;
  height: 40px;
}

.chat-container {
  padding: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid #e4e7ed;
  flex-shrink: 0;
  transition: width 0.1s ease;
}

.resizer {
  width: 5px;
  background-color: #e4e7ed;
  cursor: col-resize;
  position: relative;
  flex-shrink: 0;
  transition: background-color 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.resizer:hover {
  background-color: #409eff;
}

.resizer-handle {
  width: 3px;
  height: 40px;
  background-color: #c0c4cc;
  border-radius: 2px;
  transition: background-color 0.2s;
}

.resizer:hover .resizer-handle {
  background-color: #409eff;
}

.view-container {
  padding: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex: 1; /* 自动填充剩余空间 */
  min-width: 300px;
  transition: width 0.1s ease;
}
</style>

