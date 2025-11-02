<template>
  <div class="thumbnail-list">
    <div class="thumbnail-header">
      <el-text size="small">内容列表 ({{ slides.length }})</el-text>
    </div>
    
    <div class="thumbnail-container">
      <div
        v-for="slide in slides"
        :key="slide.slide_number"
        class="thumbnail-item"
        :class="{ active: slide.slide_number === currentSlideNumber }"
        @click="handleSlideClick(slide.slide_number)"
      >
        <div class="thumbnail-number">{{ slide.slide_number }}</div>
        <div class="thumbnail-content">
          <div class="thumbnail-title" v-if="slide.title">
            {{ slide.title }}
          </div>
          <div class="thumbnail-preview">
            {{ getTextPreview(slide.text_content) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue'

const props = defineProps({
  slides: {
    type: Array,
    required: true,
    default: () => []
  },
  currentSlideNumber: {
    type: Number,
    default: 1
  }
})

const emit = defineEmits(['slide-change'])

const handleSlideClick = (slideNumber) => {
  emit('slide-change', slideNumber)
}

const getTextPreview = (text) => {
  if (!text) return '（无文本内容）'
  // 取前100个字符，并去除换行
  const preview = text.replace(/\n/g, ' ').trim()
  return preview.length > 100 ? preview.substring(0, 100) + '...' : preview
}
</script>

<style scoped>
.thumbnail-list {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #f5f5f5;
}

.thumbnail-header {
  padding: 12px;
  border-bottom: 1px solid #e4e7ed;
  background-color: #fff;
}

.thumbnail-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.thumbnail-item {
  display: flex;
  margin-bottom: 8px;
  padding: 12px;
  background-color: #fff;
  border: 2px solid transparent;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.thumbnail-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 4px rgba(64, 158, 255, 0.2);
}

.thumbnail-item.active {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.thumbnail-number {
  min-width: 32px;
  height: 32px;
  line-height: 32px;
  text-align: center;
  background-color: #409eff;
  color: #fff;
  border-radius: 4px;
  font-weight: bold;
  font-size: 14px;
  margin-right: 12px;
  flex-shrink: 0;
}

.thumbnail-item.active .thumbnail-number {
  background-color: #66b1ff;
}

.thumbnail-content {
  flex: 1;
  min-width: 0;
}

.thumbnail-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thumbnail-preview {
  font-size: 12px;
  color: #606266;
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* 滚动条样式 */
.thumbnail-container::-webkit-scrollbar {
  width: 6px;
}

.thumbnail-container::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.thumbnail-container::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.thumbnail-container::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>

