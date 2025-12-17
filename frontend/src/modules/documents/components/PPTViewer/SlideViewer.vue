<template>
  <div class="slide-viewer" ref="slideViewerRef">
    <div class="slide-container" v-if="slides.length > 0">
      <div
        v-for="(slide, index) in slides"
        :key="slide.slide_number || index"
        :ref="el => { if (el) slideRefs[index] = el }"
        class="slide-item"
        :class="{ 'current-slide': slide.slide_number === currentSlideNumber }"
        @click="onSlideClick(slide.slide_number)"
      >
        <img
          :src="getSlideImageUrl(slide.slide_number)"
          :alt="`Slide ${slide.slide_number}`"
          class="slide-image"
          @load="handleImageLoad"
        />
      </div>
    </div>
    <div v-else class="empty-slide">
      <span>暂无幻灯片内容</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
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
  fileId: {
    type: String,
    default: ''
  },
  fileExtension: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['slide-change'])

const slideViewerRef = ref(null)
const slideRefs = ref([])

const getSlideImageUrl = (slideNumber) => {
  if (!props.conversationId || !props.fileId || !slideNumber) return ''
  return documentService.getSlideImageUrl(
    props.conversationId,
    props.fileId,
    slideNumber
  )
}

const handleImageLoad = () => {
  // 图片加载完成后的处理
}

const onSlideClick = (slideNumber) => {
  if (!slideNumber) return
  emit('slide-change', slideNumber)
}

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
</style>


