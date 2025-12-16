<template>
  <div class="slide-viewer">
    <div class="slide-container" v-if="currentSlideImageUrl">
      <img :src="currentSlideImageUrl" alt="Slide" class="slide-image" />
    </div>
    <div v-else class="empty-slide">
      <span>暂无幻灯片内容</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
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

const currentSlideImageUrl = computed(() => {
  if (!props.conversationId || !props.fileId || !props.currentSlideNumber) return ''
  return documentService.getSlideImageUrl(
    props.conversationId,
    props.fileId,
    props.currentSlideNumber
  )
})
</script>

<style scoped>
.slide-viewer {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f5f5f5;
}

.slide-container {
  max-width: 100%;
  max-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.slide-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  border-radius: 4px;
}

.empty-slide {
  color: #909399;
  font-size: 14px;
}
</style>


