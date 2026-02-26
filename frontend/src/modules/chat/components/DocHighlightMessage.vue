<template>
  <div class="doc-highlight-message">
    <div class="highlight-card">
      <div class="card-icon">
        <el-icon><Document /></el-icon>
      </div>
      <div class="card-content">
        <div class="card-title">{{ filename }}</div>
        <div class="card-page">第 {{ pageNumber }} {{ pageLabel }}</div>
      </div>
      <button class="card-close" type="button" @click="handleClose">
        <el-icon><Close /></el-icon>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Document, Close } from '@element-plus/icons-vue'

const props = defineProps({
  filename: {
    type: String,
    required: true
  },
  pageNumber: {
    type: Number,
    required: true
  },
  fileExtension: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['close'])

const pageLabel = computed(() => {
  return props.fileExtension === 'pdf' ? '页' : '张幻灯片'
})

const handleClose = () => {
  emit('close')
}
</script>

<style scoped>
.doc-highlight-message {
  margin: 4px 0;
}

.highlight-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background-color: #f5f7fa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  transition: all 0.2s;
  font-size: 15px;
  line-height: 1.4;
}

.highlight-card:hover {
  background-color: #edf0f5;
  border-color: #d3d6de;
}

.card-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background-color: #409eff;
  border-radius: 6px;
  color: white;
  flex-shrink: 0;
}

.card-icon .el-icon {
  font-size: 16px;
}

.card-content {
  flex: 1;
  min-width: 0;
}

.card-title {
  font-weight: 500;
  color: #303133;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-page {
  font-size: 13px;
  color: #909399;
}

.card-close {
  border: none;
  background: transparent;
  padding: 2px;
  margin-left: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: #a0a3aa;
  flex-shrink: 0;
}

.card-close .el-icon {
  font-size: 14px;
}

.card-close:hover {
  background-color: #e4e7ed;
  color: #606266;
}
</style>
