<template>
  <div class="doc-image-message">
    <div class="image-card">
      <div class="card-header">
        <div class="header-info">
          <el-icon class="header-icon"><Picture /></el-icon>
          <span class="header-text">{{ filename }} - 第 {{ pageNumber }} {{ pageLabel }}</span>
        </div>
        <el-icon class="close-icon" @click="handleClose"><Close /></el-icon>
      </div>
      <div class="card-image-wrapper">
        <img :src="imageUrl" :alt="`${filename} - 第 ${pageNumber} ${pageLabel}`" class="card-image" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Picture, Close } from '@element-plus/icons-vue'

const props = defineProps({
  filename: {
    type: String,
    required: true
  },
  pageNumber: {
    type: Number,
    required: true
  },
  imageUrl: {
    type: String,
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
.doc-image-message {
  margin: 12px 0;
}

.image-card {
  background-color: #fafafa;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.2s;
}

.image-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background-color: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.header-icon {
  font-size: 16px;
  color: #409eff;
  flex-shrink: 0;
}

.header-text {
  font-size: 13px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.close-icon {
  font-size: 16px;
  color: #909399;
  cursor: pointer;
  flex-shrink: 0;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}

.close-icon:hover {
  background-color: #e4e7ed;
  color: #303133;
}

.card-image-wrapper {
  padding: 12px;
  display: flex;
  justify-content: center;
  background-color: white;
}

.card-image {
  max-width: 100%;
  max-height: 200px;
  height: auto;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}
</style>
