<template>
  <div class="thumbnail-list">
    <!-- 收起按钮（放在顶部） -->
    <div class="collapse-header">
      <el-button
        size="small"
        :icon="ArrowLeft"
        circle
        @click="handleCollapse"
        title="收起目录"
      />
    </div>
    
    <!-- 缩略图列表 -->
    <div
      v-for="slide in slides"
      :key="slide.slide_number"
      class="thumbnail-item"
      :class="{ active: slide.slide_number === currentSlideNumber }"
      @click="$emit('slide-change', slide.slide_number)"
    >
      <div class="thumbnail-number">{{ slide.slide_number }}</div>
    </div>
  </div>
</template>

<script setup>
import { ArrowLeft } from '@element-plus/icons-vue'

const props = defineProps({
  slides: {
    type: Array,
    default: () => []
  },
  currentSlideNumber: {
    type: Number,
    default: 1
  }
})

// 定义 emit
const emit = defineEmits(['slide-change', 'toggle-sidebar'])

// 处理收起按钮点击
const handleCollapse = () => {
  emit('toggle-sidebar')
}
</script>

<style scoped>
.thumbnail-list {
  height: 100%;
  overflow-y: auto;
  padding: 8px;
  background-color: #f5f5f5;
  display: flex;
  flex-direction: column;
}

.collapse-header {
  padding: 8px;
  display: flex;
  justify-content: flex-end;
  border-bottom: 1px solid #e4e7ed;
  margin-bottom: 8px;
  flex-shrink: 0;
}

.thumbnail-item {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  margin-bottom: 8px;
  border-radius: 4px;
  background-color: #ffffff;
  border: 1px solid #e4e7ed;
  cursor: pointer;
  transition: all 0.2s;
}

.thumbnail-item:hover {
  border-color: #409eff;
}

.thumbnail-item.active {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.thumbnail-number {
  font-size: 14px;
  color: #606266;
}
</style>


