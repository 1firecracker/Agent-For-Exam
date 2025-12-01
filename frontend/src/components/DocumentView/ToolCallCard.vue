<template>
  <div class="tool-call-card" :class="cardClass">
    <div class="tool-call-header" @click="toggleExpand">
      <div class="tool-info">
        <el-icon class="tool-icon" :class="iconClass">
          <component :is="toolIcon" />
        </el-icon>
        <div class="tool-details">
          <div class="tool-name">{{ toolName }}</div>
          <div class="tool-status">
            <el-tag :type="statusTagType" size="small">{{ statusText }}</el-tag>
            <span class="tool-time">{{ formatTime(timestamp) }}</span>
          </div>
        </div>
      </div>
      <el-icon class="expand-icon" :class="{ 'expanded': expanded }">
        <ArrowDown />
      </el-icon>
    </div>
    
    <el-collapse-transition>
      <div v-show="expanded" class="tool-call-content">
        <!-- 工具参数 -->
        <div v-if="toolArguments && Object.keys(toolArguments).length > 0" class="tool-section">
          <div class="section-title">调用参数</div>
          <pre class="tool-arguments">{{ formatArguments(toolArguments) }}</pre>
        </div>
        
        <!-- 执行结果 -->
        <div v-if="result" class="tool-section">
          <div class="section-title">执行结果</div>
          <div v-if="result.status === 'success'" class="result-success">
            <div class="result-message">{{ result.message || '执行成功' }}</div>
            <div v-if="result.result && typeof result.result === 'object'" class="result-details">
              <pre>{{ JSON.stringify(result.result, null, 2) }}</pre>
            </div>
            <div v-else-if="result.result" class="result-details">
              {{ result.result }}
            </div>
          </div>
          <div v-else-if="result.status === 'error'" class="result-error">
            <div class="result-message">{{ result.message || '执行失败' }}</div>
            <div v-if="result.error" class="result-details">
              <pre>{{ result.error }}</pre>
            </div>
          </div>
        </div>
        
        <!-- 错误信息 -->
        <div v-if="errorMessage" class="tool-section">
          <div class="section-title">错误信息</div>
          <div class="result-error">
            <pre>{{ errorMessage }}</pre>
          </div>
        </div>
      </div>
    </el-collapse-transition>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ArrowDown, Tools, Connection, Document, Search } from '@element-plus/icons-vue'

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
  timestamp: {
    type: Number,
    default: () => Date.now()
  },
  status: {
    type: String,
    default: 'pending', // pending, success, error
    validator: (value) => ['pending', 'success', 'error'].includes(value)
  }
})

const expanded = ref(false)

const toggleExpand = () => {
  expanded.value = !expanded.value
}

// 计算状态文本
const statusText = computed(() => {
  if (props.errorMessage) return '错误'
  if (props.result?.status === 'success') return '成功'
  if (props.result?.status === 'error') return '失败'
  return '执行中'
})

// 计算状态标签类型
const statusTagType = computed(() => {
  if (props.errorMessage || props.result?.status === 'error') return 'danger'
  if (props.result?.status === 'success') return 'success'
  return 'warning'
})

// 计算卡片样式类
const cardClass = computed(() => {
  if (props.errorMessage || props.result?.status === 'error') return 'tool-call-error'
  if (props.result?.status === 'success') return 'tool-call-success'
  return 'tool-call-pending'
})

// 计算图标样式类
const iconClass = computed(() => {
  if (props.errorMessage || props.result?.status === 'error') return 'icon-error'
  if (props.result?.status === 'success') return 'icon-success'
  return 'icon-pending'
})

// 根据工具名称返回对应的图标
const toolIcon = computed(() => {
  const iconMap = {
    'generate_mindmap': Connection,
    'search_knowledge_graph': Search,
    'get_document_content': Document,
  }
  return iconMap[props.toolName] || Tools
})

// 格式化参数
const formatArguments = (args) => {
  try {
    return JSON.stringify(args, null, 2)
  } catch (e) {
    return String(args)
  }
}

// 格式化时间
const formatTime = (timestamp) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  })
}
</script>

<style scoped>
.tool-call-card {
  margin: 12px 0;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  background-color: #fff;
  overflow: hidden;
  transition: all 0.3s;
}

.tool-call-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.tool-call-card.tool-call-success {
  border-left: 4px solid #67c23a;
}

.tool-call-card.tool-call-error {
  border-left: 4px solid #f56c6c;
}

.tool-call-card.tool-call-pending {
  border-left: 4px solid #e6a23c;
}

.tool-call-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
}

.tool-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.tool-icon {
  font-size: 20px;
  color: #909399;
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

.tool-details {
  flex: 1;
}

.tool-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
}

.tool-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-time {
  font-size: 12px;
  color: #909399;
}

.expand-icon {
  font-size: 16px;
  color: #909399;
  transition: transform 0.3s;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.tool-call-content {
  padding: 0 16px 16px 16px;
  border-top: 1px solid #f0f0f0;
  margin-top: 8px;
  padding-top: 16px;
}

.tool-section {
  margin-bottom: 16px;
}

.tool-section:last-child {
  margin-bottom: 0;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tool-arguments,
.result-details pre {
  background-color: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 12px;
  font-size: 12px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  color: #303133;
  overflow-x: auto;
  margin: 0;
  line-height: 1.6;
}

.result-success {
  color: #67c23a;
}

.result-success .result-message {
  font-weight: 500;
  margin-bottom: 8px;
}

.result-error {
  color: #f56c6c;
}

.result-error .result-message {
  font-weight: 500;
  margin-bottom: 8px;
}

.result-details {
  margin-top: 8px;
}
</style>

