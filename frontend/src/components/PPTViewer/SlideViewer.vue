<template>
  <div class="slide-viewer">
    <!-- 工具栏 -->
    <div class="slide-toolbar">
      <div class="toolbar-left">
        <el-button-group>
          <el-button 
            :disabled="currentSlideNumber <= 1"
            @click="handlePrevious"
            :icon="ArrowLeft"
          >
            上一张
          </el-button>
          <el-button 
            :disabled="currentSlideNumber >= totalSlides"
            @click="handleNext"
            :icon="ArrowRight"
          >
            下一张
          </el-button>
        </el-button-group>
        
        <el-text class="slide-counter">
          第 {{ currentSlideNumber }} / {{ totalSlides }} 项
        </el-text>
      </div>
      
      <div class="toolbar-right">
        <el-button-group>
          <el-button @click="handleZoomOut" :icon="ZoomOut">缩小</el-button>
          <el-text class="zoom-text">{{ Math.round(props.zoomLevel * 100) }}%</el-text>
          <el-button @click="handleZoomIn" :icon="ZoomIn">放大</el-button>
          <el-button @click="handleResetZoom">重置</el-button>
        </el-button-group>
      </div>
    </div>

    <!-- 幻灯片内容区域 -->
    <div class="slide-content-container" :style="{ transform: `scale(${props.zoomLevel})` }">
      <div class="slide-content-wrapper" v-if="slide">
        <!-- 渲染的图片（背景层） -->
        <div class="slide-image-container" v-if="imageUrl && enableImageRender">
          <img
            :src="imageUrl"
            :alt="slide.title || `幻灯片 ${currentSlideNumber}`"
            class="slide-image"
            @load="onImageLoad"
            @error="onImageError"
            :style="{ display: imageLoaded ? 'block' : 'none' }"
          />
          <div v-if="!imageLoaded && !imageError" class="image-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>加载中...</span>
          </div>
          <div v-if="imageError" class="image-error">
            <el-icon><WarningFilled /></el-icon>
            <span>图片加载失败</span>
          </div>
          
          <!-- 简单高亮层（HTML绝对定位） -->
          <!-- 仅支持PPTX的文本位置高亮，PDF禁用高亮功能 -->
          <SimpleHighlightLayer
            v-if="enableCanvasTextLayer && imageLoaded && isHighlightEnabled && slide.text_positions && slide.text_positions.length > 0 && slide.slide_dimensions"
            :text-positions="slide.text_positions"
            :slide-dimensions="slide.slide_dimensions"
            :image-loaded="imageLoaded"
            @entity-click="handleEntityClick"
          />
        </div>

        <!-- 文本层（叠加在图片上方，用于实体标注和文本选择） -->
        <div class="slide-text-layer" :class="{ 'text-selectable': showTextLayer }" v-if="showTextLayer">
          <div class="slide-title" v-if="slide.title">
            {{ slide.title }}
          </div>
          <div 
            class="slide-text" 
            v-html="highlightedText"
          ></div>
        </div>

        <!-- 降级显示：如果图片加载失败或未启用图片渲染，显示文本内容 -->
        <div v-if="imageError || !enableImageRender" class="slide-fallback">
          <!-- 幻灯片标题 -->
          <div class="slide-title" v-if="slide.title">
            {{ slide.title }}
          </div>

          <!-- 文本内容 -->
          <div class="slide-text" v-html="highlightedText"></div>

          <!-- 图片占位框 -->
          <div v-if="slide.images && slide.images.length > 0" class="slide-images">
            <div
              v-for="(image, index) in slide.images"
              :key="index"
              class="image-placeholder"
            >
              <el-icon class="image-icon"><Picture /></el-icon>
              <div class="image-info">
                <div class="image-alt">{{ image.alt_text || `图片 ${index + 1}` }}</div>
                <div class="image-size">位置: ({{ formatPosition(image.position) }})</div>
              </div>
            </div>
          </div>

          <!-- 结构信息 -->
          <div v-if="slide.structure" class="slide-structure">
            <el-tag size="small">布局: {{ slide.structure.layout || '未知' }}</el-tag>
            <el-tag size="small" style="margin-left: 8px;">
              元素数: {{ slide.structure.shapes_count || 0 }}
            </el-tag>
          </div>
        </div>
      </div>

      <el-empty v-else description="暂无幻灯片内容" />
    </div>
  </div>
</template>

<script setup>
import { computed, watch, ref, onMounted, onUnmounted } from 'vue'
import { ArrowLeft, ArrowRight, ZoomIn, ZoomOut, Picture, Loading, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useGraphStore } from '../../stores/graphStore'
import documentService from '../../services/documentService'
import SimpleHighlightLayer from './SimpleHighlightLayer.vue'

const props = defineProps({
  slide: {
    type: Object,
    default: null
  },
  currentSlideNumber: {
    type: Number,
    required: true
  },
  totalSlides: {
    type: Number,
    required: true
  },
  zoomLevel: {
    type: Number,
    default: 1
  },
  conversationId: {
    type: String,
    required: true
  },
  fileId: {
    type: String,
    required: true
  },
  fileExtension: {
    type: String,
    default: null  // 文件扩展名（用于判断是否启用高亮）
  },
  enableImageRender: {
    type: Boolean,
    default: true  // 默认启用图片渲染
  },
  showTextLayer: {
    type: Boolean,
    default: false  // 不使用简单文本层，改用Canvas精确叠加
  },
  enableCanvasTextLayer: {
    type: Boolean,
    default: true  // 启用Canvas文本层（精确位置对齐）
  }
})

const emit = defineEmits(['previous', 'next', 'zoom-change'])

const graphStore = useGraphStore()

// 图片加载状态
const imageUrl = ref('')
const imageLoaded = ref(false)
const imageError = ref(false)

// 计算属性：是否启用高亮功能（仅PPTX启用，PDF禁用）
const isHighlightEnabled = computed(() => {
  // 只有PPTX文件才启用高亮功能，PDF禁用
  return props.fileExtension === 'pptx'
})

// 高亮文本中的实体
const highlightedText = computed(() => {
  if (!props.slide || !props.slide.text_content) return ''
  
  let text = props.slide.text_content
  
  // 转义 HTML 特殊字符
  text = text.replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  
  // 高亮实体（从知识图谱中获取实体名称）
  if (graphStore.entities && graphStore.entities.length > 0) {
    // 按长度排序，优先匹配较长的实体名
    const sortedEntities = [...graphStore.entities].sort((a, b) => {
      const nameA = (a.name || a.entity_id || '').length
      const nameB = (b.name || b.entity_id || '').length
      return nameB - nameA
    })
    
    sortedEntities.forEach(entity => {
      const entityName = entity.name || entity.entity_id
      if (entityName && entityName.length > 1 && text.includes(entityName)) {
        // 转义特殊字符用于正则
        const escapedName = entityName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
        const regex = new RegExp(`(${escapedName})`, 'gi')
        text = text.replace(regex, (match) => {
          // 避免重复替换已经高亮的内容
          if (match.includes('entity-highlight')) return match
          return `<span class="entity-highlight" title="${entityName}">${match}</span>`
        })
      }
    })
  }
  
  // 将换行符转换为 <br>
  text = text.replace(/\n/g, '<br>')
  
  return text
})

const handlePrevious = () => {
  if (props.currentSlideNumber > 1) {
    emit('previous')
  }
}

const handleNext = () => {
  if (props.currentSlideNumber < props.totalSlides) {
    emit('next')
  }
}

const handleZoomIn = () => {
  const newZoom = Math.min(props.zoomLevel + 0.1, 2.0)
  emit('zoom-change', newZoom)
}

const handleZoomOut = () => {
  const newZoom = Math.max(props.zoomLevel - 0.1, 0.5)
  emit('zoom-change', newZoom)
}

const handleResetZoom = () => {
  emit('zoom-change', 1.0)
}

const formatPosition = (position) => {
  if (!position) return '未知'
  return `左:${position.left}, 上:${position.top}, 宽:${position.width}, 高:${position.height}`
}

// 加载图片
const loadImage = () => {
  if (!props.enableImageRender || !props.conversationId || !props.fileId) {
    imageError.value = true
    return
  }
  
  imageLoaded.value = false
  imageError.value = false
  
  // 生成图片URL
  imageUrl.value = documentService.getSlideImageUrl(
    props.conversationId,
    props.fileId,
    props.currentSlideNumber,
    true
  )
}

// 图片加载成功
const onImageLoad = () => {
  imageLoaded.value = true
  imageError.value = false
}

// 图片加载失败
const onImageError = () => {
  imageLoaded.value = false
  imageError.value = true
}

  // 监听幻灯片变化，重新加载图片
  watch(
    () => [props.currentSlideNumber, props.conversationId, props.fileId],
    () => {
      if (props.enableImageRender) {
        loadImage()
      }
      // 调试：检查当前幻灯片是否有text_positions
      if (props.slide) {
        if (props.slide.text_positions && props.slide.text_positions.length > 0) {
          console.log(`✅ 当前幻灯片/页面 ${props.currentSlideNumber} 的文本位置数据:`, props.slide.text_positions.length, '个文本块')
          console.log('文本位置示例:', props.slide.text_positions[0])
          if (props.slide.slide_dimensions) {
            console.log('尺寸信息:', props.slide.slide_dimensions)
          } else {
            console.warn('⚠️ 缺少尺寸信息，无法进行高亮定位')
          }
        } else {
          console.warn(`⚠️ 当前幻灯片/页面 ${props.currentSlideNumber} 没有文本位置数据 (text_positions:`, props.slide.text_positions, ')')
        }
      }
    },
    { immediate: true }
  )
  
  // 监听slide变化，打印调试信息
  watch(
    () => props.slide,
    (newSlide) => {
      if (newSlide) {
        console.log('📄 幻灯片/页面数据更新:', {
          slide_number: newSlide.slide_number,
          title: newSlide.title,
          has_text_positions: !!newSlide.text_positions,
          text_positions_count: newSlide.text_positions?.length || 0,
          has_slide_dimensions: !!newSlide.slide_dimensions,
          slide_dimensions: newSlide.slide_dimensions,
          enableCanvasTextLayer: props.enableCanvasTextLayer,
          imageLoaded: imageLoaded.value
        })
        
        // 检查是否可以启用高亮层
        const canHighlight = props.enableCanvasTextLayer && 
                            imageLoaded.value && 
                            newSlide.text_positions && 
                            newSlide.text_positions.length > 0 &&
                            newSlide.slide_dimensions &&
                            newSlide.slide_dimensions.width_pixels
        
        if (!canHighlight && newSlide.text_positions && newSlide.text_positions.length > 0) {
          console.warn('⚠️ 高亮层未启用，原因:', {
            enableCanvasTextLayer: props.enableCanvasTextLayer,
            imageLoaded: imageLoaded.value,
            hasTextPositions: !!newSlide.text_positions && newSlide.text_positions.length > 0,
            hasDimensions: !!newSlide.slide_dimensions,
            hasWidthPixels: !!newSlide.slide_dimensions?.width_pixels
          })
        }
      }
    },
    { deep: true, immediate: true }
  )

// 组件挂载时加载图片和实体数据
onMounted(async () => {
  if (props.enableImageRender) {
    loadImage()
  }
  
  // 加载知识图谱实体数据（用于Canvas实体高亮）
  if (props.conversationId) {
    try {
      console.log('📊 加载知识图谱实体数据...')
      await graphStore.loadGraph(props.conversationId)
      console.log('✅ 实体数据加载完成，实体数:', graphStore.entities.length)
      if (graphStore.entities.length > 0) {
        console.log('实体示例:', graphStore.entities[0])
      }
    } catch (error) {
      console.warn('⚠️ 加载实体数据失败:', error)
    }
  } else {
    console.warn('⚠️ 没有conversationId，无法加载实体数据')
  }
})

// 处理实体点击
const handleEntityClick = (entity) => {
  // 可以在这里添加实体点击的处理逻辑
  // 例如：显示实体详情、跳转到知识图谱等
  console.log('Entity clicked:', entity)
  
  // 使用Element Plus的消息提示
  ElMessage.info({
    message: `实体: ${entity.name || entity.entity_id}\n类型: ${entity.type || '未知'}`,
    duration: 3000
  })
  
  // TODO: 实现实体详情展示（可以打开对话框或跳转到知识图谱）
}

// 键盘快捷键支持（通过父组件传递）
// 这里不直接监听，避免多个实例冲突
</script>

<style scoped>
.slide-viewer {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #f5f5f5;
}

.slide-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.toolbar-right {
  display: flex;
  align-items: center;
}

.slide-counter {
  font-size: 14px;
  color: #606266;
}

.zoom-text {
  min-width: 50px;
  text-align: center;
  font-size: 14px;
  color: #606266;
  padding: 0 8px;
}

.slide-content-container {
  flex: 1;
  overflow: auto;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 20px;
  transform-origin: top center;
  transition: transform 0.3s ease;
}

.slide-content-wrapper {
  position: relative;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  min-width: 800px;
  max-width: 1200px;
  width: 100%;
  overflow: hidden;
}

.slide-image-container {
  position: relative;
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f5f5f5;
  min-height: 600px;
}

.slide-image {
  max-width: 100%;
  height: auto;
  display: block;
}

.image-loading,
.image-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px;
  color: #909399;
}

.image-loading .el-icon {
  font-size: 32px;
}

.image-error .el-icon {
  font-size: 32px;
  color: #f56c6c;
}

.slide-text-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  padding: 40px;
  background: transparent;
  /* 文本几乎透明，但可选中 */
  color: rgba(0, 0, 0, 0.01);
  user-select: text;
  -webkit-user-select: text;
}

.slide-text-layer.text-selectable {
  pointer-events: auto;
}

/* 实体高亮保持可见，并支持交互 */
.slide-text-layer :deep(.entity-highlight) {
  background-color: rgba(255, 243, 205, 0.7) !important;
  color: rgba(0, 0, 0, 0.9) !important;
  padding: 2px 4px;
  border-radius: 3px;
  pointer-events: auto;
  cursor: pointer;
  transition: background-color 0.2s;
}

.slide-text-layer :deep(.entity-highlight:hover) {
  background-color: rgba(255, 193, 7, 0.9) !important;
}

.slide-fallback {
  padding: 40px;
  background-color: #fff;
}

.slide-title {
  font-size: 32px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #e4e7ed;
}

.slide-text {
  font-size: 16px;
  line-height: 1.8;
  color: #606266;
  margin-bottom: 24px;
}

/* 实体高亮样式 */
:deep(.entity-highlight) {
  background-color: #fff3cd;
  padding: 2px 4px;
  border-radius: 3px;
  cursor: pointer;
  transition: background-color 0.2s;
}

:deep(.entity-highlight:hover) {
  background-color: #ffc107;
}

.slide-images {
  margin: 24px 0;
}

.image-placeholder {
  display: flex;
  align-items: center;
  padding: 16px;
  margin-bottom: 12px;
  border: 2px dashed #dcdfe6;
  border-radius: 4px;
  background-color: #f5f7fa;
}

.image-icon {
  font-size: 32px;
  color: #909399;
  margin-right: 16px;
}

.image-info {
  flex: 1;
}

.image-alt {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
}

.image-size {
  font-size: 12px;
  color: #909399;
}

.slide-structure {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #e4e7ed;
}

/* 滚动条样式 */
.slide-content-container::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.slide-content-container::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.slide-content-container::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

.slide-content-container::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>

