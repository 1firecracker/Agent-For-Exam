<template>
  <div class="slide-viewer" ref="slideViewerRef" @click="handleContainerClick">
    <div class="slide-container" v-if="slides.length > 0">
      <div
        v-for="(slide, index) in slides"
        :key="slide.slide_number || index"
        :ref="el => { if (el) slideRefs[index] = el }"
        class="slide-item"
        :class="{ 'current-slide': slide.slide_number === currentSlideNumber }"
        @click="onSlideClick(slide.slide_number)"
        @dblclick="handleSlideDblClick($event, slide, index)"
      >
        <img
          :src="getSlideImageUrl(slide.slide_number)"
          :alt="`Slide ${slide.slide_number}`"
          class="slide-image"
          @load="handleImageLoad"
          @error="handleImageError"
        />
      </div>
    </div>
    <div v-else class="empty-slide">
      <span>暂无幻灯片内容</span>
    </div>
    
    <!-- 气泡菜单 -->
    <div
      v-if="bubbleState.visible"
      class="bubble-menu"
      :style="{ left: bubbleState.x + 'px', top: bubbleState.y + 'px' }"
      @click.stop
    >
      <div class="bubble-menu-item" @click="handleLoadParsed">
        <el-icon><Document /></el-icon>
        <span>载入解析数据</span>
      </div>
      <div class="bubble-menu-item" @click="handleLoadImage">
        <el-icon><Picture /></el-icon>
        <span>载入图片</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick, onUnmounted } from 'vue'
import { Document, Picture } from '@element-plus/icons-vue'
import documentService from '../../services/documentService'

const props = defineProps({
  slides: {
    type: Array,
    default: () => []
  },
  currentSlideNumber: {
    type: Number,
    default: 1
  },
  totalSlides: {
    type: Number,
    default: 0
  },
  conversationId: {
    type: String,
    default: ''
  },
  subjectId: {
    type: String,
    default: ''
  },
  fileId: {
    type: String,
    default: ''
  },
  fileExtension: {
    type: String,
    default: ''
  },
  filename: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['slide-change', 'request-load-parsed', 'request-load-image'])

const slideViewerRef = ref(null)
const slideRefs = ref([])

// 气泡菜单状态
const bubbleState = ref({
  visible: false,
  x: 0,
  y: 0,
  fileId: '',
  filename: '',
  pageNumber: null
})

// 防止双击后的 click 事件关闭气泡菜单
const doubleClickTimeout = ref(null)
const isDoubleClicking = ref(false)

const getSlideImageUrl = (slideNumber) => {
  if (!props.fileId || !slideNumber) return ''
  
  // 优先使用 subjectId
  if (props.subjectId) {
    return documentService.getSlideImageUrlForSubject(
      props.subjectId,
      props.fileId,
      slideNumber
    )
  }
  // 回退到 conversationId
  if (props.conversationId) {
    return documentService.getSlideImageUrl(
      props.conversationId,
      props.fileId,
      slideNumber
    )
  }
  return ''
}

const handleImageLoad = () => {
  // 图片加载完成后的处理
}

const handleImageError = (event) => {
  // 图片加载失败处理
}

const onSlideClick = (slideNumber) => {
  // 如果正在双击或双击后的短暂时间内，忽略 click 事件（防止关闭气泡菜单）
  if (isDoubleClicking.value || doubleClickTimeout.value) {
    return
  }
  
  if (!slideNumber) return
  emit('slide-change', slideNumber)
}


// 处理双击事件
const handleSlideDblClick = (event, slide, slideIndex) => {
  event.stopPropagation()
  event.preventDefault()
  
  if (!slide || !props.fileId) {
    return
  }
  
  // 设置双击标志
  isDoubleClicking.value = true
  
  // 清除之前的超时（如果有）
  if (doubleClickTimeout.value) {
    clearTimeout(doubleClickTimeout.value)
  }
  
  // 设置一个延迟，防止双击后的 click 事件关闭气泡菜单
  // 使用更长的超时时间（500ms），因为某些浏览器双击后的 click 事件可能延迟触发
  doubleClickTimeout.value = setTimeout(() => {
    doubleClickTimeout.value = null
    isDoubleClicking.value = false
  }, 500)
  
  // 获取被点击的 slide-item 元素
  const slideItem = slideRefs.value[slideIndex]
  const slideViewer = slideViewerRef.value
  
  if (!slideItem || !slideViewer) {
    return
  }
  
  // 获取 slide-item 相对于 slide-viewer 的位置
  const slideItemRect = slideItem.getBoundingClientRect()
  const slideViewerRect = slideViewer.getBoundingClientRect()
  
  // 计算点击位置相对于 slide-item 的坐标
  const relativeX = event.clientX - slideItemRect.left
  const relativeY = event.clientY - slideItemRect.top
  
  // 计算 slide-item 相对于 slide-viewer 的位置（考虑滚动）
  const slideViewerScrollLeft = slideViewer.scrollLeft || 0
  const slideViewerScrollTop = slideViewer.scrollTop || 0
  const slideItemOffsetX = slideItemRect.left - slideViewerRect.left + slideViewerScrollLeft
  const slideItemOffsetY = slideItemRect.top - slideViewerRect.top + slideViewerScrollTop
  
  // 最终坐标 = slide-item 在 slide-viewer 中的位置 + 点击在 slide-item 中的相对位置
  const x = slideItemOffsetX + relativeX
  const y = slideItemOffsetY + relativeY
  
  // 更新气泡状态
  bubbleState.value = {
    visible: true,
    x,
    y,
    fileId: props.fileId,
    filename: props.filename || '',
    pageNumber: slide.slide_number
  }
}

// 处理容器点击（关闭气泡）
const handleContainerClick = (event) => {
  // 如果正在双击或双击后的短暂时间内，忽略 click 事件（防止关闭气泡菜单）
  if (isDoubleClicking.value || doubleClickTimeout.value) {
    return
  }
  
  // 如果点击的不是气泡菜单本身，则关闭
  if (!event.target.closest('.bubble-menu')) {
    bubbleState.value.visible = false
  }
}

// 处理"载入解析数据"
const handleLoadParsed = () => {
  if (!bubbleState.value.fileId || !bubbleState.value.pageNumber) return
  
  emit('request-load-parsed', {
    fileId: bubbleState.value.fileId,
    filename: bubbleState.value.filename,
    pageNumber: bubbleState.value.pageNumber
  })
  
  bubbleState.value.visible = false
}

// 处理"载入图片"
const handleLoadImage = () => {
  if (!bubbleState.value.fileId || !bubbleState.value.pageNumber) return
  
  emit('request-load-image', {
    fileId: bubbleState.value.fileId,
    filename: bubbleState.value.filename,
    pageNumber: bubbleState.value.pageNumber
  })
  
  bubbleState.value.visible = false
}

// 监听 ESC 键关闭气泡
const handleKeyDown = (event) => {
  if (event.key === 'Escape' && bubbleState.value.visible) {
    bubbleState.value.visible = false
  }
}

// 监听滚动关闭气泡
const handleScroll = () => {
  if (bubbleState.value.visible) {
    bubbleState.value.visible = false
  }
}

watch(() => bubbleState.value.visible, (visible) => {
  if (visible) {
    window.addEventListener('keydown', handleKeyDown)
    slideViewerRef.value?.addEventListener('scroll', handleScroll)
  } else {
    window.removeEventListener('keydown', handleKeyDown)
    slideViewerRef.value?.removeEventListener('scroll', handleScroll)
  }
})

// 组件卸载时清理事件监听器
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  if (slideViewerRef.value) {
    slideViewerRef.value.removeEventListener('scroll', handleScroll)
  }
  // 清理超时
  if (doubleClickTimeout.value) {
    clearTimeout(doubleClickTimeout.value)
  }
})

// 当 currentSlideNumber 改变时，滚动到对应的幻灯片
watch(() => props.currentSlideNumber, (newNumber) => {
  nextTick(() => {
    const slideIndex = props.slides.findIndex(s => s.slide_number === newNumber)
    if (slideIndex !== -1 && slideRefs.value[slideIndex] && slideViewerRef.value) {
      slideRefs.value[slideIndex].scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      })
    }
  })
}, { immediate: false })
</script>

<style scoped>
.slide-viewer {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  background-color: #f5f5f5;
  padding: 20px;
  position: relative; /* 确保气泡菜单的 absolute 定位相对于此容器 */
}

.slide-container {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.slide-item {
  width: 100%;
  display: flex;
  justify-content: center;
  padding: 10px 0;
  cursor: pointer;
}

.slide-item.current-slide {
  background-color: rgba(64, 158, 255, 0.1);
  border-radius: 4px;
}

.slide-image {
  max-width: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  border-radius: 4px;
}

.empty-slide {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: #909399;
  font-size: 14px;
}

/* 气泡菜单样式 */
.bubble-menu {
  position: absolute;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 8px 0;
  min-width: 160px;
  z-index: 1000;
  transform: translate(-50%, -100%);
  margin-top: -8px;
}

.bubble-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background-color 0.2s;
  font-size: 14px;
  color: #303133;
}

.bubble-menu-item:hover {
  background-color: #f5f7fa;
}

.bubble-menu-item .el-icon {
  font-size: 16px;
  color: #409eff;
}
</style>


