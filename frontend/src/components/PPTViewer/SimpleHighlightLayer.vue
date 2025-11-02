<template>
  <div class="highlight-layer-container" ref="containerRef">
    <!-- 实体高亮矩形 -->
    <div
      v-for="(highlight, index) in entityHighlights"
      :key="index"
      class="entity-highlight-box"
      :class="{ 'hovered': hoveredEntity === highlight.entity }"
      :style="getHighlightStyle(highlight)"
      @mouseenter="handleMouseEnter(highlight.entity, $event)"
      @mouseleave="handleMouseLeave"
      @mousemove="handleMouseMove($event)"
      @click="handleClick(highlight.entity)"
    ></div>
    
    <!-- 实体提示框 -->
    <div
      v-if="hoveredEntity && tooltipPosition"
      class="entity-tooltip"
      :style="{
        left: tooltipPosition.x + 'px',
        top: tooltipPosition.y + 'px'
      }"
    >
      <div class="tooltip-title">{{ hoveredEntity.name || hoveredEntity.entity_id }}</div>
      <div class="tooltip-type">类型: {{ hoveredEntity.type || '未知' }}</div>
      <div v-if="hoveredEntity.description" class="tooltip-desc">{{ hoveredEntity.description }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useGraphStore } from '../../stores/graphStore'

const props = defineProps({
  textPositions: {
    type: Array,
    default: () => []
  },
  slideDimensions: {
    type: Object,
    default: null
  },
  imageLoaded: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['entity-click'])

const containerRef = ref(null)
const hoveredEntity = ref(null)
const tooltipPosition = ref(null)
const graphStore = useGraphStore()

// 检查文本是否包含实体
const checkEntityInText = (text, entities) => {
  if (!entities || entities.length === 0) return null
  
  // 按长度排序，优先匹配较长的实体名
  const sortedEntities = [...entities].sort((a, b) => {
    const nameA = (a.name || a.entity_id || '').length
    const nameB = (b.name || b.entity_id || '').length
    return nameB - nameA
  })
  
  for (const entity of sortedEntities) {
    const entityName = entity.name || entity.entity_id
    if (entityName && entityName.length > 1 && text.includes(entityName)) {
      return entity
    }
  }
  return null
}

// 计算实体高亮区域（使用百分比定位）
const entityHighlights = computed(() => {
  if (!props.textPositions || props.textPositions.length === 0) {
    console.warn('[SimpleHighlightLayer] 没有文本位置数据')
    return []
  }
  
  if (!props.slideDimensions || !props.slideDimensions.width_pixels) {
    console.warn('[SimpleHighlightLayer] 没有尺寸信息', props.slideDimensions)
    return []
  }
  
  const entities = graphStore.entities || []
  if (entities.length === 0) {
    console.warn('[SimpleHighlightLayer] 没有实体数据，无法进行高亮')
    return []
  }
  
  const highlights = []
  
  // 基准尺寸（文本位置基于的像素尺寸）
  const baseWidth = props.slideDimensions.width_pixels
  const baseHeight = props.slideDimensions.height_pixels
  
  // 调试信息
  console.log(`[SimpleHighlightLayer] 处理 ${props.textPositions.length} 个文本块，基准尺寸: ${baseWidth} × ${baseHeight}px`)
  
  props.textPositions.forEach((textItem, index) => {
    // 检查文本位置格式
    if (!textItem.text || !textItem.position) {
      console.warn(`[SimpleHighlightLayer] 文本块 ${index} 格式不正确:`, textItem)
      return
    }
    
    const entity = checkEntityInText(textItem.text, entities)
    if (entity) {
      // 计算百分比位置（相对于基准尺寸）
      const xPercent = (textItem.position.x / baseWidth) * 100
      const yPercent = (textItem.position.y / baseHeight) * 100
      const widthPercent = (textItem.position.width / baseWidth) * 100
      const heightPercent = (textItem.position.height / baseHeight) * 100
      
      // 验证计算结果
      if (isNaN(xPercent) || isNaN(yPercent) || isNaN(widthPercent) || isNaN(heightPercent)) {
        console.error(`[SimpleHighlightLayer] 计算百分比失败:`, {
          text: textItem.text,
          position: textItem.position,
          baseWidth,
          baseHeight
        })
        return
      }
      
      highlights.push({
        entity,
        xPercent,
        yPercent,
        widthPercent,
        heightPercent,
        position: textItem.position
      })
    }
  })
  
  console.log(`[SimpleHighlightLayer] 找到 ${highlights.length} 个实体高亮区域`)
  return highlights
})

// 获取高亮样式
const getHighlightStyle = (highlight) => {
  return {
    left: `${highlight.xPercent}%`,
    top: `${highlight.yPercent}%`,
    width: `${highlight.widthPercent}%`,
    height: `${highlight.heightPercent}%`
  }
}

// 鼠标进入
const handleMouseEnter = (entity, event) => {
  hoveredEntity.value = entity
  if (containerRef.value && event) {
    const rect = containerRef.value.getBoundingClientRect()
    tooltipPosition.value = {
      x: event.clientX - rect.left + 10,
      y: event.clientY - rect.top - 10
    }
  }
}

// 鼠标移动（更新提示框位置）
const handleMouseMove = (event) => {
  if (hoveredEntity.value && containerRef.value) {
    const rect = containerRef.value.getBoundingClientRect()
    tooltipPosition.value = {
      x: event.clientX - rect.left + 10,
      y: event.clientY - rect.top - 10
    }
  }
}

// 鼠标离开
const handleMouseLeave = () => {
  hoveredEntity.value = null
  tooltipPosition.value = null
}

// 点击处理
const handleClick = (entity) => {
  emit('entity-click', entity)
}

// 监听图片加载状态，确保容器尺寸正确
watch(
  () => props.imageLoaded,
  (loaded) => {
    if (loaded) {
      // 图片加载完成后，容器尺寸会自动适配
      // 百分比定位会自动适应
    }
  }
)
</script>

<style scoped>
.highlight-layer-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 10;
}

.entity-highlight-box {
  position: absolute;
  background-color: rgba(255, 243, 205, 0.5);
  border: 1px solid rgba(255, 193, 7, 0.3);
  pointer-events: auto;
  cursor: pointer;
  transition: background-color 0.2s, border-color 0.2s;
  box-sizing: border-box;
}

.entity-highlight-box:hover,
.entity-highlight-box.hovered {
  background-color: rgba(255, 193, 7, 0.6);
  border-color: rgba(255, 193, 7, 0.8);
  border-width: 2px;
}

/* 实体提示框 */
.entity-tooltip {
  position: absolute;
  background-color: rgba(0, 0, 0, 0.85);
  color: white;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 12px;
  z-index: 1000;
  pointer-events: none;
  max-width: 300px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.tooltip-title {
  font-weight: bold;
  font-size: 14px;
  margin-bottom: 4px;
  color: #ffc107;
}

.tooltip-type {
  font-size: 11px;
  color: #ccc;
  margin-bottom: 4px;
}

.tooltip-desc {
  font-size: 11px;
  color: #eee;
  margin-top: 4px;
  line-height: 1.4;
}
</style>

