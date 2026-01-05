<template>
  <div class="ppt-viewer">
    <el-card class="viewer-card" shadow="never">
      <template #header>
        <div class="viewer-header">
          <div class="header-left">
            <el-select
              v-model="selectedFileId"
              placeholder="选择文档（PPTX/PDF）"
              style="width: 300px"
              @change="handleFileChange"
              :loading="loading"
            >
              <el-option
                v-for="doc in supportedDocuments"
                :key="doc.file_id"
                :label="`${doc.filename} (${doc.file_extension.toUpperCase()})`"
                :value="doc.file_id"
              />
            </el-select>
          </div>
          <div class="header-right">
            <el-button
              v-if="conversationStore.currentConversationId"
              @click="showGraphDialog = true"
              :icon="Connection"
            >
              查看知识图谱
            </el-button>
            <el-button
              v-if="selectedFileId"
              @click="handleRefresh"
              :loading="loading"
              :icon="Refresh"
            >
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <div class="viewer-content">
        <transition name="slide-fade">
          <div v-show="!collapsed" class="sidebar">
            <ThumbnailList
              :slides="slides"
              :current-slide-number="currentSlideNumber"
              @slide-change="handleSlideChange"
              @toggle-sidebar="toggleSidebar"
            />
          </div>
        </transition>

        <div class="main-content" :class="{ 'sidebar-collapsed': collapsed }">
          <el-button
            v-if="collapsed"
            class="expand-sidebar-btn"
            @click="toggleSidebar"
            :icon="ArrowRight"
            circle
          />
          
          <SlideViewer
            :slides="slides"
            :current-slide-number="currentSlideNumber"
            :total-slides="slides.length"
            :conversation-id="conversationStore.currentConversationId"
            :file-id="selectedFileId"
            :file-extension="currentFileExtension"
            @slide-change="handleSlideChange"
          />
        </div>
      </div>
    </el-card>
    
    <el-dialog
      v-model="showGraphDialog"
      title="知识图谱"
      width="90%"
      :close-on-click-modal="false"
      class="graph-dialog"
    >
      <GraphViewer v-if="conversationStore.currentConversationId" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, ArrowLeft, ArrowRight, Connection } from '@element-plus/icons-vue'
import { useDocumentStore } from '../../store/documentStore'
import { useConversationStore } from '../../../chat/store/conversationStore'
import GraphViewer from '../../../graph/components/GraphViewer.vue'
import ThumbnailList from './ThumbnailList.vue'
import SlideViewer from './SlideViewer.vue'

const props = defineProps({
  defaultFileId: {
    type: String,
    default: null
  }
})

const documentStore = useDocumentStore()
const conversationStore = useConversationStore()

const loading = ref(false)
const slides = ref([])
const currentSlideNumber = ref(1)
const collapsed = ref(true)
const selectedFileId = ref(props.defaultFileId || null)
const showGraphDialog = ref(false)

watch(() => props.defaultFileId, (newFileId) => {
  if (newFileId && newFileId !== selectedFileId.value) {
    selectedFileId.value = newFileId
    loadSlides()
  }
}, { immediate: true })

const supportedDocuments = computed(() => {
  if (!conversationStore.currentConversationId) return []
  
  const docs = documentStore.getDocumentsByConversation(conversationStore.currentConversationId)
  return docs.filter(doc => ['pptx', 'pdf'].includes(doc.file_extension))
})

const currentSlide = computed(() => {
  if (slides.value.length === 0) return null
  return slides.value.find(s => s.slide_number === currentSlideNumber.value) || slides.value[0]
})

const currentFileExtension = computed(() => {
  if (!selectedFileId.value) return null
  const doc = supportedDocuments.value.find(d => d.file_id === selectedFileId.value)
  return doc?.file_extension || null
})

const loadSlides = async () => {
  if (!selectedFileId.value || !conversationStore.currentConversationId) {
    slides.value = []
    return
  }

  loading.value = true
  try {
    const response = await documentStore.getDocumentSlides(
      conversationStore.currentConversationId,
      selectedFileId.value
    )
    slides.value = response.slides || []
    
    if (slides.value.length > 0) {
      currentSlideNumber.value = 1
      const doc = supportedDocuments.value.find(d => d.file_id === selectedFileId.value)
      const docType = doc?.file_extension === 'pdf' ? '页' : '张幻灯片'
      ElMessage.success(`加载成功，共 ${slides.value.length} ${docType}`)
    } else {
      ElMessage.warning('该文档没有内容')
    }
  } catch (error) {
    console.error('Load slides failed:', error)
    ElMessage.error('加载幻灯片失败')
    slides.value = []
  } finally {
    loading.value = false
  }
}

const handleFileChange = () => {
  currentSlideNumber.value = 1
  loadSlides()
}

const handleSlideChange = (slideNumber) => {
  currentSlideNumber.value = slideNumber
}

const jumpToPage = (pageNumber) => {
  if (pageNumber >= 1 && pageNumber <= slides.value.length) {
    currentSlideNumber.value = pageNumber
  }
}

const loadDocumentAndJump = async (fileId, pageNumber) => {
  if (!fileId || !conversationStore.currentConversationId) return

  // 如果是不同文档，先切换文档并加载对应的 slides
  if (fileId !== selectedFileId.value) {
    selectedFileId.value = fileId
    await loadSlides()
  } else if (!slides.value.length) {
    // 同一个文档但还没有加载过页列表，也需要先加载
    await loadSlides()
  }

  if (pageNumber >= 1 && pageNumber <= slides.value.length) {
    currentSlideNumber.value = pageNumber
  }
}

defineExpose({
  jumpToPage,
  loadDocumentAndJump
})

const handlePrevious = () => {
  if (currentSlideNumber.value > 1) {
    currentSlideNumber.value--
  }
}

const handleNext = () => {
  if (currentSlideNumber.value < slides.value.length) {
    currentSlideNumber.value++
  }
}

const handleRefresh = () => {
  loadSlides()
}

const toggleSidebar = () => {
  collapsed.value = !collapsed.value
}

watch(
  () => conversationStore.currentConversationId,
  async (newId, oldId) => {
    if (newId && newId !== oldId) {
      selectedFileId.value = null
      slides.value = []
      currentSlideNumber.value = 1
      
      await documentStore.loadDocuments(newId)
      
      if (supportedDocuments.value.length > 0) {
        selectedFileId.value = supportedDocuments.value[0].file_id
        await loadSlides()
      }
    } else if (!newId) {
      selectedFileId.value = null
      slides.value = []
    }
  },
  { immediate: true }
)

const handleKeyDown = (event) => {
  if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
    return
  }
  
  if (event.key === 'ArrowLeft') {
    handlePrevious()
  } else if (event.key === 'ArrowRight') {
    handleNext()
  }
}

onMounted(async () => {
  window.addEventListener('keydown', handleKeyDown)
  
  if (conversationStore.currentConversationId) {
    await documentStore.loadDocuments(conversationStore.currentConversationId)
    if (supportedDocuments.value.length > 0) {
      selectedFileId.value = supportedDocuments.value[0].file_id
      await loadSlides()
    }
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<style scoped>
.ppt-viewer {
  width: 100%;
  height: 100%;
}

.viewer-card {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.viewer-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}

.viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
}

.viewer-card :deep(.el-card__header) {
  padding: 8px 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  width: fit-content;
  min-width: 320px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.viewer-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.sidebar {
  width: 320px;
  min-width: 280px;
  border-right: 1px solid #e4e7ed;
  transition: width 0.3s;
}

.main-content {
  flex: 1;
  overflow: hidden;
  transition: margin-left 0.3s;
  position: relative;
}

.main-content.sidebar-collapsed {
  margin-left: 0;
}

.expand-sidebar-btn {
  position: absolute;
  top: 80px;
  left: 16px;
  z-index: 1000;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
}

.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.3s ease;
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  width: 0 !important;
  opacity: 0;
}

@media (max-width: 768px) {
  .sidebar {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 100;
    background-color: #fff;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
  }
  
  .main-content.sidebar-collapsed .sidebar {
    display: none;
  }
}
</style>


