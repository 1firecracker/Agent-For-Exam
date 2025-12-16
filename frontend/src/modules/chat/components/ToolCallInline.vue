<template>
  <div class="tool-call-inline" :class="statusClass">
    <div class="tool-call-content">
      <el-icon class="tool-icon" :class="iconClass">
        <component :is="toolIcon" />
      </el-icon>
      <div class="tool-info">
        <div class="tool-name-row">
          <span class="tool-name">{{ toolName }}</span>
          <span v-if="status === 'pending'" class="status-text status-pending">
            <el-icon class="loading-icon"><Loading /></el-icon>
            执行中...
          </span>
          <span v-else-if="status === 'success'" class="status-text status-success">成功</span>
          <span v-else-if="status === 'error'" class="status-text status-error">失败</span>
        </div>
        <div v-if="progress && status === 'pending'" class="tool-progress">
          <div class="progress-bar">
            <div 
              class="progress-fill" 
              :style="{ width: `${progress.percentage}%` }"
            ></div>
          </div>
          <div class="progress-text">{{ progress.message }}</div>
        </div>
        <div v-if="showDetails && (toolArguments || result || errorMessage)" class="tool-details">
          <div v-if="toolArguments && Object.keys(toolArguments).length > 0" class="detail-item">
            <span class="detail-label">参数:</span>
            <span class="detail-value">{{ formatArguments(toolArguments) }}</span>
          </div>
          <div v-if="result" class="detail-item">
            <span class="detail-label">结果:</span>
            <span class="detail-value">{{ result.message || '执行成功' }}</span>
          </div>
          <div v-if="errorMessage" class="detail-item">
            <span class="detail-label">错误:</span>
            <span class="detail-value error-text">{{ errorMessage }}</span>
          </div>
        </div>
      </div>
      <el-icon v-if="hasDetails" class="expand-icon" :class="{ 'expanded': expanded }" @click.stop="toggleExpand">
        <ArrowDown />
      </el-icon>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ArrowDown, Tools, Connection, Document, Search, Loading } from '@element-plus/icons-vue'

const props = defineProps({
  toolName: {
    type: String,
    required: true
  },
  toolArguments: {
    type: Object,
    default: () => ({})
  },
  result: {
    type: Object,
    default: null
  },
  errorMessage: {
    type: String,
    default: null
  },
  status: {
    type: String,
    default: 'pending',
    validator: (value) => ['pending', 'success', 'error'].includes(value)
  },
  progress: {
    type: Object,
    default: null
  }
})

const expanded = ref(false)

const toggleExpand = () => {
  expanded.value = !expanded.value
}

const statusClass = computed(() => {
  if (props.errorMessage || props.status === 'error') return 'status-error'
  if (props.status === 'success') return 'status-success'
  return 'status-pending'
})

const iconClass = computed(() => {
  if (props.errorMessage || props.status === 'error') return 'icon-error'
  if (props.status === 'success') return 'icon-success'
  return 'icon-pending'
})

const toolIcon = computed(() => {
  const iconMap = {
    'generate_mindmap': Connection,
    'search_knowledge_graph': Search,
    'list_documents': Document,
    'get_document_content': Document,
  }
  return iconMap[props.toolName] || Tools
})

const hasDetails = computed(() => {
  return (props.toolArguments && Object.keys(props.toolArguments).length > 0) ||
         props.result ||
         props.errorMessage
})

const showDetails = computed(() => {
  return expanded.value && hasDetails.value
})

const formatArguments = (args) => {
  try {
    const str = JSON.stringify(args, null, 0)
    return str.length > 50 ? str.substring(0, 50) + '...' : str
  } catch (e) {
    return String(args)
  }
}
</script>

<style scoped>
.tool-call-inline {
  margin: 8px 0;
  border-radius: 8px;
  background-color: #f5f7fa;
  border: 1px solid #e4e7ed;
  transition: all 0.2s;
}

.tool-call-inline.status-success {
  background-color: #f0f9ff;
  border-color: #67c23a;
}

.tool-call-inline.status-error {
  background-color: #fef0f0;
  border-color: #f56c6c;
}

.tool-call-inline.status-pending {
  background-color: #fdf6ec;
  border-color: #e6a23c;
}

.tool-call-content {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
}

.tool-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.tool-icon.icon-success {
  color: #67c23a;
}

.tool-icon.icon-error {
  color: #f56c6c;
}

.tool-icon.icon-pending {
  color: #e6a23c;
}

.tool-info {
  flex: 1;
  min-width: 0;
}

.tool-name-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.tool-name {
  font-weight: 500;
  font-size: 14px;
  color: #303133;
}

.status-text {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 500;
}

.status-text.status-success {
  background-color: #67c23a;
  color: #fff;
}

.status-text.status-error {
  background-color: #f56c6c;
  color: #fff;
}

.status-text.status-pending {
  background-color: #e6a23c;
  color: #fff;
}

.tool-details {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e4e7ed;
  font-size: 12px;
}

.detail-item {
  margin-bottom: 4px;
  display: flex;
  gap: 8px;
}

.detail-item:last-child {
  margin-bottom: 0;
}

.detail-label {
  color: #909399;
  font-weight: 500;
  min-width: 40px;
}

.detail-value {
  color: #606266;
  flex: 1;
  word-break: break-word;
}

.detail-value.error-text {
  color: #f56c6c;
}

.expand-icon {
  font-size: 14px;
  color: #909399;
  cursor: pointer;
  transition: transform 0.2s;
  flex-shrink: 0;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.expand-icon:hover {
  color: #606266;
}

.loading-icon {
  animation: rotate 1s linear infinite;
  margin-right: 4px;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.tool-progress {
  margin-top: 8px;
}

.progress-bar {
  width: 100%;
  height: 6px;
  background-color: #e4e7ed;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 6px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #e6a23c 0%, #f0c78a 100%);
  border-radius: 3px;
  transition: width 0.3s ease;
  animation: shimmer 1.5s ease-in-out infinite;
}

@keyframes shimmer {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
  100% {
    opacity: 1;
  }
}

.progress-text {
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
}
</style>



