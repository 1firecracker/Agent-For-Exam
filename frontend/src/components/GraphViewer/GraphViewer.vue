<template>
  <el-card class="graph-viewer-card">
    <template #header>
      <div class="viewer-header">
        <div class="header-left">
          <h3>知识图谱</h3>
          <el-text v-if="graphStore.hasData" class="graph-stats">
            实体: {{ graphStore.totalEntities }} | 关系: {{ graphStore.totalRelations }}
          </el-text>
        </div>
        <div class="header-right">
          <el-button 
            :icon="filtersCollapsed ? ArrowRight : ArrowLeft" 
            circle 
            plain 
            size="small" 
            @click="toggleFilters"
            title="折叠/展开过滤"
          />
          <el-button 
            :icon="Refresh" 
            circle 
            plain 
            size="small" 
            @click="handleRefresh"
            :loading="graphStore.loading"
            title="刷新图谱"
          />
        </div>
      </div>
    </template>
    
    <!-- 横向布局：过滤组件 + 知识图谱 -->
    <div class="graph-content-wrapper">
      <!-- 过滤组件：可折叠 -->
      <div 
        class="filters-container"
        :class="{ 'collapsed': filtersCollapsed }"
      >
        <div v-if="!filtersCollapsed" class="filters-content-wrapper">
          <GraphFilters @filter-change="handleFilterChange" />
        </div>
        <div 
          v-else 
          class="filters-collapsed-bar"
          @click="toggleFilters"
        >
          <el-icon class="collapse-icon"><ArrowRight /></el-icon>
          <span class="collapse-text">过滤</span>
        </div>
      </div>
      
      <!-- 知识图谱：自动填充剩余空间 -->
      <div class="canvas-container">
        <GraphCanvas 
          :conversation-id="conversationId"
          :filter-options="filterOptions"
          @node-click="handleNodeClick"
          @node-hover="handleNodeHover"
          @doc-click="handleDocClick"
        />
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Refresh, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { useGraphStore } from '../../stores/graphStore'
import { useConversationStore } from '../../stores/conversationStore'
import { useDocumentStore } from '../../stores/documentStore'
import GraphCanvas from './GraphCanvas.vue'
import GraphFilters from './GraphFilters.vue'
import { ElMessage } from 'element-plus'

const graphStore = useGraphStore()
const conversationStore = useConversationStore()
const documentStore = useDocumentStore()

const conversationId = computed(() => conversationStore.currentConversationId)

// 过滤区域折叠状态（默认展开）
const filtersCollapsed = ref(false)

// 过滤选项
const filterOptions = ref({
  searchText: '',
  selectedTypes: [],
  minDegree: 0
})

// 切换过滤区域折叠状态
const toggleFilters = () => {
  filtersCollapsed.value = !filtersCollapsed.value
}

const handleRefresh = async () => {
  if (conversationId.value) {
    await graphStore.loadGraph(conversationId.value)
  }
}

const handleNodeClick = (entity) => {
  console.log('节点点击:', entity)
}

const handleNodeHover = (entity) => {
  console.log('节点悬停:', entity)
}

// 处理过滤变化
const handleFilterChange = (options) => {
  filterOptions.value = options
}

// 处理文档点击
const handleDocClick = (doc) => {
  if (conversationId.value && doc.file_id) {
    ElMessage.info(`跳转到文档: ${doc.filename}`)
    // TODO: 可以触发切换到 PPT 查看器，并打开对应文档
    // 例如：触发父组件事件，切换到对应的标签页和文档
    console.log('文档点击:', doc)
  }
}
</script>

<style scoped>
.graph-viewer-card {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 600px;
}

.graph-viewer-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
  min-height: 600px;
}

.graph-content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: row;
  gap: 12px;
  padding: 12px;
  overflow: hidden;
  min-height: 0; /* 允许子元素缩小 */
}

.filters-container {
  width: 20%; /* 1/5 宽度 */
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
  transition: width 0.3s ease;
  border-right: 1px solid #e4e7ed;
}

.filters-container.collapsed {
  width: 40px;
}

.filters-content-wrapper {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.filters-collapsed-bar {
  width: 100%;
  height: 100%;
  background-color: #f5f5f5;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: 12px 4px;
  cursor: pointer;
  transition: background-color 0.2s;
  writing-mode: vertical-lr; /* 垂直文字 */
}

.filters-collapsed-bar:hover {
  background-color: #ecf5ff;
}

.collapse-icon {
  font-size: 18px;
  color: #409eff;
  margin-bottom: 8px;
}

.collapse-text {
  font-size: 12px;
  color: #606266;
  letter-spacing: 2px;
}

.canvas-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.graph-stats {
  font-size: 12px;
  color: #909399;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>

