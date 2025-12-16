<template>
  <div class="documents-dashboard">
    <!-- 顶部标题区 -->
    <header class="page-header">
      <div class="header-left">
        <h2 class="page-title">
          <el-icon><Document /></el-icon>
          Documents
        </h2>
        <p class="page-subtitle">Manage context sources for {{ currentSubjectName }}.</p>
      </div>
      <div class="header-right">
        <el-button 
          type="primary" 
          size="large" 
          round
          class="start-chat-btn"
          @click="startChat"
        >
          <el-icon><ChatLineRound /></el-icon>
          Start Chatting
        </el-button>
      </div>
    </header>

    <!-- 上传区域 -->
    <section class="upload-section">
      <el-upload
        class="upload-dropzone"
        drag
        :http-request="handleUpload"
        :before-upload="handleBeforeUpload"
        :multiple="true"
        :show-file-list="false"
      >
        <div class="dropzone-content">
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div class="upload-text">
            <strong>Click to upload</strong> or drag PDF/PPTX files here
          </div>
          <div class="upload-hint">Support PDF, PPTX (Max 50MB)</div>
        </div>
      </el-upload>
    </section>

    <!-- 文档列表区域 -->
    <section class="documents-list-section">
      <div v-if="docStore.loading" class="loading-state">
        <el-skeleton :rows="3" animated />
      </div>

      <div v-else-if="currentDocuments.length === 0" class="empty-state">
        <el-empty description="No documents uploaded yet. Start by adding some context." :image-size="120" />
      </div>

      <div v-else class="documents-grid">
        <div 
          v-for="doc in currentDocuments" 
          :key="doc.file_id" 
          class="document-card"
        >
          <div class="doc-icon-wrapper">
             <span class="file-type">{{ getFileType(doc.filename) }}</span>
          </div>
          
          <div class="doc-info">
            <h3 class="doc-title" :title="doc.filename">{{ doc.filename }}</h3>
            <div class="doc-meta">
              <span class="doc-size">{{ formatFileSize(doc.file_size) }}</span>
              <span class="doc-status" :class="doc.status">
                <span class="status-dot"></span>
                {{ doc.status }}
              </span>
            </div>
          </div>

          <div class="doc-actions">
            <el-button link type="primary" @click="testGetDocumentStatus(doc.file_id)">Details</el-button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, UploadFilled, ChatLineRound } from '@element-plus/icons-vue'
import { useConversationStore } from '../modules/chat/store/conversationStore'
import { useDocumentStore } from '../modules/documents/store/documentStore'

const route = useRoute()
const router = useRouter()
const convStore = useConversationStore()
const docStore = useDocumentStore()

const subjectId = route.params.id

const currentSubjectName = computed(() => {
  return convStore.currentConversation?.title || 'this subject'
})

const currentDocuments = computed(() => {
  return docStore.getDocumentsByConversation(subjectId)
})

onMounted(async () => {
  if (subjectId) {
    // 确保 Conversation 被选中
    if (!convStore.currentConversationId || convStore.currentConversationId !== subjectId) {
      await convStore.loadConversation(subjectId)
      convStore.selectConversation(subjectId)
    }
    await docStore.loadDocuments(subjectId)
  }
})

// 监听路由变化，如果 ID 变了，重新加载
watch(() => route.params.id, async (newId) => {
  if (newId) {
    await convStore.loadConversation(newId)
    convStore.selectConversation(newId)
    await docStore.loadDocuments(newId)
  }
})

const startChat = () => {
  router.push(`/chat/${subjectId}`)
}

const getFileType = (filename) => {
  if (filename.endsWith('.pdf')) return 'PDF'
  if (filename.endsWith('.pptx')) return 'PPT'
  return 'DOC'
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const handleBeforeUpload = (file) => {
  const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.presentationml.presentation']
  if (!allowedTypes.includes(file.type)) {
    ElMessage.error('Only PDF and PPTX files are supported.')
    return false
  }
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error('File size cannot exceed 50MB.')
    return false
  }
  return true
}

const handleUpload = async (options) => {
  const { file } = options
  try {
    await docStore.uploadDocuments(subjectId, file)
    ElMessage.success('Upload started')
    await docStore.loadDocuments(subjectId)
  } catch (error) {
    console.error('Upload failed:', error)
    ElMessage.error('Upload failed')
  }
}

const testGetDocumentStatus = async (fileId) => {
  try {
    const status = await docStore.getDocumentStatus(subjectId, fileId)
    ElMessage.info(`Current status: ${status.status}`)
  } catch (error) {
    console.error('Get status failed:', error)
  }
}
</script>

<style scoped>
.documents-dashboard {
  max-width: 900px;
  margin: 0 auto;
}

/* Header */
.page-header {
  margin-bottom: 32px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.page-title {
  font-family: var(--font-serif);
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.page-subtitle {
  font-family: var(--font-sans);
  color: var(--text-secondary);
  font-size: 15px;
}

.start-chat-btn {
  background-color: var(--color-accent);
  border-color: var(--color-accent);
  font-weight: 600;
  padding: 12px 24px;
}

.start-chat-btn:hover {
  background-color: var(--color-accent-hover);
  border-color: var(--color-accent-hover);
}

.start-chat-btn :deep(.el-icon) {
  margin-right: 8px;
}

/* Upload Zone */
.upload-section {
  margin-bottom: 40px;
}

.upload-dropzone :deep(.el-upload-dragger) {
  background-color: var(--bg-card);
  border: 2px dashed var(--border-subtle);
  border-radius: 12px;
  padding: 40px 20px;
  transition: all 0.2s;
}

.upload-dropzone :deep(.el-upload-dragger:hover) {
  border-color: var(--color-accent);
  background-color: var(--color-accent-light);
}

.dropzone-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.upload-icon {
  font-size: 48px;
  color: var(--text-tertiary);
  margin-bottom: 8px;
}

.upload-text {
  font-size: 16px;
  color: var(--text-primary);
}

.upload-text strong {
  color: var(--color-accent);
  cursor: pointer;
}

.upload-hint {
  font-size: 13px;
  color: var(--text-tertiary);
}

/* Grid */
.documents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.document-card {
  background-color: var(--bg-card);
  border-radius: 12px;
  padding: 20px;
  box-shadow: var(--shadow-card);
  display: flex;
  align-items: center;
  gap: 16px;
  transition: transform 0.2s, box-shadow 0.2s;
  border: 1px solid transparent;
}

.document-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-float);
  border-color: var(--border-subtle);
}

.doc-icon-wrapper {
  width: 48px;
  height: 48px;
  background-color: #F3F4F6;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  color: var(--text-secondary);
}

.doc-info {
  flex: 1;
  overflow: hidden;
}

.doc-title {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.doc-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.doc-status {
  display: flex;
  align-items: center;
  gap: 6px;
  text-transform: capitalize;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #D1D5DB;
}

.doc-status.processing .status-dot { background-color: #F59E0B; }
.doc-status.completed .status-dot { background-color: #10B981; }
.doc-status.failed .status-dot { background-color: #EF4444; }

.doc-status.processing { color: #D97706; }
.doc-status.completed { color: #059669; }
.doc-status.failed { color: #DC2626; }

.doc-actions {
  opacity: 0;
  transition: opacity 0.2s;
}

.document-card:hover .doc-actions {
  opacity: 1;
}
</style>
