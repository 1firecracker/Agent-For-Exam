<template>
  <div class="canvas-text-layer-container" ref="containerRef">
    <canvas
      ref="canvasRef"
      class="canvas-text-layer"
      :style="canvasStyle"
      @mousemove="handleMouseMove"
      @click="handleClick"
      @mouseleave="handleMouseLeave"
    ></canvas>
    
    <!-- 实体提示框（悬浮显示） -->
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
    
    <!-- 调试模式：显示文本区域边框（可选） -->
    <div v-if="debugMode" class="debug-info">
      文本块数: {{ textPositions.length }} | 
      实体数: {{ entityCount }}
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { useGraphStore } from '../../stores/graphStore'

const props = defineProps({
  textPositions: {
    type: Array,
    default: () => []
  },
  imageUrl: {
    type: String,
    default: ''
  },
  imageLoaded: {
    type: Boolean,
    default: false
  },
  zoomLevel: {
    type: Number,
    default: 1
  },
  slide: {
    type: Object,
    default: null
  },
  slideDimensions: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['entity-click'])

const canvasRef = ref(null)
const containerRef = ref(null)
const hoveredEntity = ref(null)
const tooltipPosition = ref(null)
const debugMode = ref(false)  // 调试模式，显示文本区域
const graphStore = useGraphStore()
const hoveredTextItem = ref(null)  // 当前鼠标悬浮的文本项

// 工具函数：四舍五入
const round = (value, decimals = 2) => {
  return Math.round(value * Math.pow(10, decimals)) / Math.pow(10, decimals)
}

// Canvas样式：需要匹配图片的显示方式
const canvasStyle = computed(() => ({
  // 不在这里应用缩放，因为图片容器已经应用了缩放
  // transform会在容器层面统一处理
}))

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

// 绘制Canvas
const drawCanvas = async () => {
  if (!canvasRef.value || !props.imageLoaded) {
    return
  }
  
  // 如果没有文本位置数据，不绘制（但不报错）
  if (!props.textPositions || props.textPositions.length === 0) {
    console.log('Canvas文本层: 没有文本位置数据')
    return
  }
  
  console.log(`Canvas文本层: 开始绘制，文本块数: ${props.textPositions.length}`)
  
  const canvas = canvasRef.value
  const ctx = canvas.getContext('2d')
  
  // 等待图片加载以获取尺寸
  const img = new Image()
  img.crossOrigin = 'anonymous'  // 允许跨域图片加载
  
  img.onload = () => {
    // 获取图片的真实尺寸和显示尺寸
    const imgWidth = img.naturalWidth || img.width
    const imgHeight = img.naturalHeight || img.height
    
    // 获取容器的显示尺寸
    const container = containerRef.value
    const displayWidth = container ? container.offsetWidth : imgWidth
    const displayHeight = container ? container.offsetHeight : imgHeight
    
    // 计算缩放比例
    const scaleX = displayWidth / imgWidth
    const scaleY = displayHeight / imgHeight
    
    // ✅ 获取幻灯片尺寸信息（从props.slide或props.slideDimensions）
    const slideDimensions = props.slideDimensions || props.slide?.slide_dimensions
    
    // 设置Canvas的显示尺寸（CSS）
    canvas.style.width = displayWidth + 'px'
    canvas.style.height = displayHeight + 'px'
    
    // 设置Canvas的实际绘制尺寸（匹配图片真实尺寸）
    canvas.width = imgWidth
    canvas.height = imgHeight
    
    // ✅ 计算文本位置的缩放比例（与鼠标事件使用完全相同的逻辑）
    const canvasActualWidth = canvas.width  // 与鼠标事件中的 canvasActualWidth 保持一致
    let textPositionScale = 1.0  // 默认不缩放
    let dpiInfo = {}
    
    // slideDimensions 已在上面声明，这里直接使用
    
    if (slideDimensions && slideDimensions.width_pixels) {
      // ✅ 使用与鼠标事件完全相同的计算：Canvas实际宽度 / 文本位置基准宽度
      textPositionScale = canvasActualWidth / slideDimensions.width_pixels
      
      dpiInfo = {
        canvasActualWidth: canvasActualWidth,
        imgWidth: imgWidth,
        baseWidth: slideDimensions.width_pixels,
        scale: round(textPositionScale, 4),
        slideWidthInches: slideDimensions.width_inches,
        slideHeightInches: slideDimensions.height_inches,
        baseDPI: slideDimensions.dpi || 150
      }
    } else {
      // ⚠️ 降级：使用与鼠标事件完全相同的固定比例
      textPositionScale = canvasActualWidth / 1500
      dpiInfo = {
        warning: '使用默认比例（可能不准确）',
        canvasActualWidth: canvasActualWidth,
        defaultScale: round(textPositionScale, 4)
      }
    }
    
    console.log('Canvas尺寸信息:', {
      imgSize: { width: imgWidth, height: imgHeight },
      displaySize: { width: displayWidth, height: displayHeight },
      scale: { x: round(scaleX, 4), y: round(scaleY, 4) },
      dpiInfo: dpiInfo,
      textPositionScale: round(textPositionScale, 4)
    })
    
    // 清除画布
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    
    // 设置文本样式
    ctx.textBaseline = 'top'
    ctx.textAlign = 'left'
    
    // 获取实体列表
    const entities = graphStore.entities || []
    
    // 绘制每个文本块
    props.textPositions.forEach((textItem, index) => {
      const { text, position, font_size } = textItem
      
      // 缩放文本位置到Canvas实际尺寸
      const scaledX = position.x * textPositionScale
      const scaledY = position.y * textPositionScale
      const scaledWidth = position.width * textPositionScale
      const scaledHeight = position.height * textPositionScale
      const scaledFontSize = (font_size || 16) * textPositionScale
      
      // 检查是否包含实体
      const entity = checkEntityInText(text, entities)
      
      if (entity) {
        // ✅ 仅保留实体高亮背景（不绘制文本）
        ctx.fillStyle = hoveredEntity.value === entity 
          ? 'rgba(255, 193, 7, 0.6)'  // 悬浮时稍深一点
          : 'rgba(255, 243, 205, 0.5)'  // 默认稍透明，不遮挡原图
        ctx.fillRect(scaledX, scaledY, scaledWidth, scaledHeight)
      } else {
        // 普通文本不显示任何内容（包括高亮和文本）
        // 仅在调试模式下显示边框
      }
      
      // 调试模式：绘制文本区域边框（用于定位）
      if (debugMode.value) {
        ctx.strokeStyle = entity ? 'rgba(255, 0, 0, 0.8)' : 'rgba(0, 0, 255, 0.3)'
        ctx.lineWidth = 1
        ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight)
        
        // 调试：在实体区域显示文本标记
        if (entity && index < 5) {
          ctx.fillStyle = 'rgba(255, 0, 0, 0.9)'
          ctx.font = `${Math.min(scaledFontSize * 0.7, 12)}px monospace`
          ctx.fillText(`${index}:${entity.name?.substring(0, 10) || 'entity'}`, scaledX, scaledY - 5)
        }
      }
      
      // ✅ 不再绘制文本内容，仅保留高亮效果
    })
    
    console.log('Canvas绘制完成，实体数:', entities.length)
    if (entities.length === 0) {
      console.warn('⚠️ 没有实体数据，无法进行实体高亮。请确保已加载知识图谱。')
      console.warn('💡 提示：可以在SlideViewer组件挂载时调用 graphStore.loadGraph(conversationId)')
    } else {
      // 调试：显示找到的实体
      const foundEntities = []
      props.textPositions.forEach(textItem => {
        const entity = checkEntityInText(textItem.text, entities)
        if (entity) foundEntities.push(entity.name || entity.entity_id)
      })
      if (foundEntities.length > 0) {
        console.log('✅ 在文本中找到的实体:', foundEntities)
      } else {
        console.log('ℹ️ 当前幻灯片文本中未找到实体')
      }
    }
  }
  
  img.onerror = () => {
    console.error('Canvas文本层: 图片加载失败')
  }
  
  if (props.imageUrl) {
    img.src = props.imageUrl
  }
}

// 鼠标移动处理（用于高亮实体和文本区域）
const handleMouseMove = (event) => {
  if (!canvasRef.value || !props.textPositions || props.textPositions.length === 0) return
  
  const canvas = canvasRef.value
  const rect = canvas.getBoundingClientRect()
  
  // 计算鼠标在Canvas中的坐标（考虑缩放）
  // Canvas的显示尺寸和实际尺寸可能不同，需要转换
  const canvasDisplayWidth = rect.width
  const canvasDisplayHeight = rect.height
  const canvasActualWidth = canvas.width
  const canvasActualHeight = canvas.height
  
  const scaleX = canvasActualWidth / canvasDisplayWidth
  const scaleY = canvasActualHeight / canvasDisplayHeight
  
  // 鼠标在Canvas实际坐标系统中的位置（不需要除以zoomLevel，因为Canvas已经考虑了）
  const x = (event.clientX - rect.left) * scaleX
  const y = (event.clientY - rect.top) * scaleY
  
  // ✅ 计算文本位置的缩放比例（与绘制时使用相同的逻辑）
  let textPositionScale = 1.0
  const slideDimensions = props.slideDimensions || props.slide?.slide_dimensions
  
  if (slideDimensions && slideDimensions.width_pixels) {
    // ✅ 使用像素比例：实际Canvas宽度 / 文本位置基准宽度
    textPositionScale = canvasActualWidth / slideDimensions.width_pixels
  } else {
    // ⚠️ 降级：使用默认比例
    textPositionScale = canvasActualWidth / 1500
  }
  
  // 查找鼠标位置下的文本
  const entities = graphStore.entities || []
  let foundEntity = null
  let foundTextItem = null
  
  for (const textItem of props.textPositions) {
    const { text, position } = textItem
    // 缩放文本位置到Canvas实际坐标
    const scaledX = position.x * textPositionScale
    const scaledY = position.y * textPositionScale
    const scaledWidth = position.width * textPositionScale
    const scaledHeight = position.height * textPositionScale
    
    if (x >= scaledX && x <= scaledX + scaledWidth &&
        y >= scaledY && y <= scaledY + scaledHeight) {
      foundTextItem = textItem
      
      // 检查是否包含实体
      const entity = checkEntityInText(text, entities)
      if (entity) {
        foundEntity = entity
        // 设置提示框位置（鼠标位置偏移）
        tooltipPosition.value = {
          x: event.clientX - rect.left + 10,
          y: event.clientY - rect.top - 10
        }
        break
      }
    }
  }
  
  // 更新悬浮状态
  const stateChanged = 
    foundEntity !== hoveredEntity.value || 
    foundTextItem !== hoveredTextItem.value
  
  if (stateChanged) {
    hoveredEntity.value = foundEntity
    hoveredTextItem.value = foundTextItem
    
    // 如果没有实体，清除提示框位置
    if (!foundEntity) {
      tooltipPosition.value = null
    }
    
    drawCanvas() // 重新绘制以更新高亮
  }
}

// 鼠标离开
const handleMouseLeave = () => {
  hoveredEntity.value = null
  hoveredTextItem.value = null
  tooltipPosition.value = null
  drawCanvas()
}

// 点击处理
const handleClick = (event) => {
  if (!canvasRef.value || !props.textPositions || props.textPositions.length === 0) return
  
  const canvas = canvasRef.value
  const rect = canvas.getBoundingClientRect()
  
  // 计算鼠标在Canvas中的坐标（考虑缩放）
  const canvasDisplayWidth = rect.width
  const canvasDisplayHeight = rect.height
  const canvasActualWidth = canvas.width
  const canvasActualHeight = canvas.height
  
  const scaleX = canvasActualWidth / canvasDisplayWidth
  const scaleY = canvasActualHeight / canvasDisplayHeight
  
  // 鼠标在Canvas实际坐标系统中的位置
  const x = (event.clientX - rect.left) * scaleX
  const y = (event.clientY - rect.top) * scaleY
  
  // ✅ 计算文本位置的缩放比例（与绘制时使用相同的逻辑）
  let textPositionScale = 1.0
  const slideDimensions = props.slideDimensions || props.slide?.slide_dimensions
  
  if (slideDimensions && slideDimensions.width_pixels) {
    // ✅ 使用像素比例：实际Canvas宽度 / 文本位置基准宽度
    textPositionScale = canvasActualWidth / slideDimensions.width_pixels
  } else {
    // ⚠️ 降级：使用默认比例
    textPositionScale = canvasActualWidth / 1500
  }
  
  // 查找点击位置的实体
  const entities = graphStore.entities || []
  
  for (const textItem of props.textPositions) {
    const { text, position } = textItem
    // 缩放文本位置到Canvas实际坐标
    const scaledX = position.x * textPositionScale
    const scaledY = position.y * textPositionScale
    const scaledWidth = position.width * textPositionScale
    const scaledHeight = position.height * textPositionScale
    
    if (x >= scaledX && x <= scaledX + scaledWidth &&
        y >= scaledY && y <= scaledY + scaledHeight) {
      const entity = checkEntityInText(text, entities)
      if (entity) {
        emit('entity-click', entity)
        break
      }
    }
  }
}

// 监听变化
watch(
  () => [props.textPositions, props.imageLoaded, props.zoomLevel, graphStore.entities],
  () => {
    nextTick(() => {
      drawCanvas()
    })
  },
  { deep: true }
)

// 计算实体数量（用于调试）
const entityCount = computed(() => {
  if (!graphStore.entities) return 0
  return graphStore.entities.length
})

// 监听键盘事件，切换调试模式（Ctrl+D）
const handleKeyDown = (event) => {
  if (event.ctrlKey && event.key === 'd') {
    event.preventDefault()
    debugMode.value = !debugMode.value
    drawCanvas()
  }
}

onMounted(async () => {
  // 如果有对话ID，尝试加载实体数据（用于实体高亮）
  // 注意：这里需要从props或store中获取conversationId
  // 暂时先绘制，实体会在watch中自动更新
  
  drawCanvas()
  // 添加键盘监听（调试模式）
  window.addEventListener('keydown', handleKeyDown)
  
  // 调试：打印实体信息
  console.log('Canvas组件挂载，当前实体数:', graphStore.entities?.length || 0)
  if (graphStore.entities && graphStore.entities.length > 0) {
    console.log('实体示例:', graphStore.entities[0])
  } else {
    console.warn('⚠️ 没有实体数据，无法进行实体高亮。请先加载知识图谱。')
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<style scoped>
.canvas-text-layer-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: auto;
  user-select: none;
  overflow: hidden;
  z-index: 10;  /* 确保在图片上方 */
}

.canvas-text-layer {
  display: block;
  width: 100%;
  height: 100%;
  pointer-events: auto;
  cursor: text;
  /* 确保Canvas可见 */
  opacity: 1;
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

/* 调试信息 */
.debug-info {
  position: absolute;
  top: 10px;
  right: 10px;
  background-color: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 11px;
  z-index: 999;
}
</style>

