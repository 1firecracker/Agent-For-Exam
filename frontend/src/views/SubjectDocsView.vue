<template>
  <div class="documents-dashboard">
    <!-- 顶部标题区 -->
    <header class="page-header">
      <div class="header-left">
        <h2 class="page-title">
          <el-icon><Document /></el-icon>
          Documents & Exams
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
          New Chatting
        </el-button>
      </div>
    </header>

    <!-- ========== 上半部分：讲义/教材 (Courseware) ========== -->
    <section class="resource-section courseware-section">
      <div class="section-header">
        <h3 class="section-title">
          <el-icon><Folder /></el-icon>
          Courseware (讲义/教材)
        </h3>
        <p class="section-desc">Upload course materials for building knowledge graph</p>
      </div>

      <!-- 上传区域 -->
      <div class="upload-section">
        <el-upload
          class="upload-dropzone"
          drag
          :http-request="handleCoursewareUpload"
          :before-upload="handleBeforeCoursewareUpload"
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
      </div>

      <!-- 文档列表 -->
      <div class="documents-list-section">
        <div v-if="docStore.loading" class="loading-state">
          <el-skeleton :rows="2" animated />
        </div>

        <div v-else-if="currentDocuments.length === 0" class="empty-state">
          <el-empty description="No courseware uploaded yet." :image-size="80" />
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
      </div>
    </section>

    <!-- ========== 分割线 ========== -->
    <el-divider class="section-divider">
      <el-icon><More /></el-icon>
    </el-divider>

    <!-- ========== 下半部分：历年试卷 (Exams) ========== -->
    <section class="resource-section exams-section">
      <div class="section-header">
        <h3 class="section-title">
          <el-icon><Edit /></el-icon>
          Exams (历年试卷)
        </h3>
        <p class="section-desc">Upload past exam papers for structured analysis</p>
      </div>

      <!-- 上传区域 -->
      <div class="upload-section">
        <el-upload
          class="upload-dropzone exam-upload"
          drag
          :http-request="handleExamUpload"
          :before-upload="handleBeforeExamUpload"
          :multiple="false"
          :show-file-list="false"
        >
          <div class="dropzone-content">
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="upload-text">
              <strong>Click to upload</strong> or drag PDF exam paper here
            </div>
            <div class="upload-hint">Support PDF only (Max 50MB)</div>
          </div>
        </el-upload>
      </div>

      <!-- 试卷列表 -->
      <div class="documents-list-section">
        <div v-if="examStore.loading" class="loading-state">
          <el-skeleton :rows="2" animated />
        </div>

        <div v-else-if="currentExams.length === 0" class="empty-state">
          <el-empty description="No exam papers uploaded yet." :image-size="80" />
        </div>

        <div v-else class="documents-grid">
          <div 
            v-for="exam in currentExams" 
            :key="exam.exam_id" 
            class="document-card exam-card"
          >
            <div class="doc-icon-wrapper exam-icon">
               <span class="file-type">EXAM</span>
            </div>
            
            <div class="doc-info">
              <h3 class="doc-title" :title="exam.title || 'Untitled'">
                {{ exam.title || 'Untitled' }}
              </h3>
              <div class="doc-meta">
                <span class="doc-year" v-if="exam.year">{{ exam.year }}年</span>
                <span class="doc-status" :class="exam.status">
                  <span class="status-dot"></span>
                  {{ getExamStatusText(exam.status) }}
                </span>
              </div>
            </div>

            <div class="doc-actions">
              <el-button 
                link 
                type="primary" 
                @click="viewExamDetail(exam.exam_id)"
                :disabled="exam.status !== 'completed'"
              >
                View
              </el-button>
              <el-button 
                link 
                type="warning" 
                @click="handleReparseExam(exam.exam_id)"
                :disabled="exam.status === 'processing'"
              >
                Reparse
              </el-button>
              <el-button 
                link 
                type="danger" 
                @click="handleDeleteExam(exam.exam_id)"
              >
                Delete
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 试卷详情抽屉 -->
    <el-drawer
      v-model="examDetailDrawerVisible"
      title="Exam Paper Details"
      direction="rtl"
      size="50%"
    >
      <div v-if="selectedExamDetail" class="exam-detail-content">
        <div class="exam-meta">
          <p><strong>Year:</strong> {{ selectedExamDetail.year }}</p>
          <p><strong>Title:</strong> {{ selectedExamDetail.title }}</p>
          <p><strong>Total Questions:</strong> {{ selectedExamDetail.questions?.length || 0 }}</p>
        </div>
        
        <el-divider />
        
        <h4>Questions Structure</h4>
        <el-tree
          :data="examQuestionsTree"
          :props="{ label: 'label', children: 'children' }"
          default-expand-all
          class="questions-tree"
          :expand-on-click-node="false"
        >
          <template #default="{ node, data }">
            <div class="custom-tree-node">
              <div class="node-header">
                <strong>{{ node.label }}</strong>
                <span v-if="data.data.score" class="node-score">
                  <el-tag size="small" effect="plain">{{ data.data.score }}</el-tag>
                </span>
              </div>
              
              <!-- 题目内容 -->
              <div class="node-content" v-if="data.data.content">
                <div v-html="formatContent(data.data.content, data.data.exam_id)"></div>
              </div>
              
              <!-- 选项 -->
              <div v-if="data.data.options && data.data.options.length" class="node-options">
                <div v-for="(opt, idx) in data.data.options" :key="idx" class="option-item">
                  {{ opt }}
                </div>
              </div>
            </div>
          </template>
        </el-tree>
      </div>
      <div v-else class="loading-state">
        <el-skeleton :rows="5" animated />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, UploadFilled, ChatLineRound, Folder, Edit, More } from '@element-plus/icons-vue'
import { useConversationStore } from '../modules/chat/store/conversationStore'
import { useDocumentStore } from '../modules/documents/store/documentStore'
import { useSubjectStore } from '../modules/subjects/store/subjectStore'
import { useExamStore } from '../modules/exams/store/examStore'
import subjectService from '../modules/subjects/services/subjectService'
import { marked } from 'marked';
import katex from 'katex';
import 'katex/dist/katex.min.css';

const route = useRoute()
const router = useRouter()
const convStore = useConversationStore()
const docStore = useDocumentStore()
const subjectStore = useSubjectStore()
const examStore = useExamStore()

const subjectId = route.params.id

// 试卷详情抽屉
const examDetailDrawerVisible = ref(false)
const selectedExamDetail = ref(null)

const currentSubjectName = computed(() => {
  return subjectStore.currentSubject?.name || 'this subject'
})

const currentDocuments = computed(() => {
  return subjectId ? docStore.getDocumentsBySubject(subjectId) : []
})

const currentExams = computed(() => {
  return examStore.exams
})

// 将试卷题目转换为树形结构
const examQuestionsTree = computed(() => {
  if (!selectedExamDetail.value?.questions) return []
  
  const convertQuestion = (q) => {
    const node = {
      label: `Q${q.index} [${q.type}]`,
      data: { ...q, exam_id: selectedExamDetail.value.id }, // 注入 exam_id 方便图片渲染
      children: []
    }
    if (q.sub_questions && q.sub_questions.length > 0) {
      node.children = q.sub_questions.map(convertQuestion)
    }
    return node
  }
  
  return selectedExamDetail.value.questions.map(convertQuestion)
})

onMounted(async () => {
  if (subjectId) {
    // 加载知识库信息
    await subjectStore.loadSubjects()
    subjectStore.selectSubject(subjectId)
    // 加载该知识库的文档
    await docStore.loadDocumentsForSubject(subjectId)
    // 加载试卷列表（按科目过滤）
    await examStore.loadExams({ subject: currentSubjectName.value })
  }
})

onUnmounted(() => {
  // 组件卸载时停止所有轮询
  examStore.stopAllPolling()
})

// 监听路由变化，如果 ID 变了，重新加载
watch(() => route.params.id, async (newId) => {
  if (newId) {
    await subjectStore.loadSubjects()
    subjectStore.selectSubject(newId)
    await docStore.loadDocumentsForSubject(newId)
    await examStore.loadExams({ subject: currentSubjectName.value })
  } else {
    docStore.clearDocumentsForSubject(subjectId)
  }
})

const startChat = async () => {
  if (!subjectId) return
  const conv = await subjectService.createConversationForSubject(subjectId)
  if (!conv || !conv.conversation_id) return
  await convStore.refreshConversation(conv.conversation_id)
  convStore.selectConversation(conv.conversation_id)
  router.push(`/subject/${subjectId}/chat/${conv.conversation_id}`)
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

const getExamStatusText = (status) => {
  const map = {
    pending: 'Pending',
    processing: 'Processing...',
    completed: 'Complete',
    failed: 'Failed'
  }
  return map[status] || status
}

// ========== Courseware 上传 ==========
const handleBeforeCoursewareUpload = (file) => {
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

const handleCoursewareUpload = async (options) => {
  const { file } = options
  if (!subjectId) {
    ElMessage.error('Cannot upload: Subject ID is missing.')
    return
  }
  try {
    await docStore.uploadDocumentsForSubject(subjectId, file)
    ElMessage.success('Upload started')
    await docStore.loadDocumentsForSubject(subjectId)
  } catch (error) {
    console.error('Upload failed:', error)
    ElMessage.error('Upload failed')
  }
}

const testGetDocumentStatus = async (fileId) => {
  try {
    if (!subjectId) return
    const status = await docStore.getDocumentStatusForSubject(subjectId, fileId)
    ElMessage.info(`Current status: ${status.status}`)
  } catch (error) {
    console.error('Get status failed:', error)
  }
}

// ========== Exam 上传 ==========
const handleBeforeExamUpload = (file) => {
  if (file.type !== 'application/pdf') {
    ElMessage.error('Only PDF files are supported for exams.')
    return false
  }
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error('File size cannot exceed 50MB.')
    return false
  }
  return true
}

const handleExamUpload = async (options) => {
  const { file } = options
  try {
    // 从文件名中尝试提取年份
    const yearMatch = file.name.match(/(\d{4})/)
    const year = yearMatch ? parseInt(yearMatch[1]) : new Date().getFullYear()
    
    await examStore.uploadExam(file, { 
      year,
      title: file.name.replace('.pdf', ''),
      subject: currentSubjectName.value
    })
    ElMessage.success('Exam upload started, parsing in progress...')
  } catch (error) {
    console.error('Exam upload failed:', error)
    ElMessage.error('Exam upload failed')
  }
}

const viewExamDetail = async (examId) => {
  examDetailDrawerVisible.value = true
  selectedExamDetail.value = null
  
  try {
    const detail = await examStore.getExamDetail(examId)
    selectedExamDetail.value = detail
  } catch (error) {
    console.error('Failed to load exam detail:', error)
    ElMessage.error('Failed to load exam details')
  }
}

const handleDeleteExam = async (examId) => {
  try {
    await ElMessageBox.confirm(
      'This will permanently delete this exam paper. Continue?',
      'Warning',
      { confirmButtonText: 'Delete', cancelButtonText: 'Cancel', type: 'warning' }
    )
    
    await examStore.deleteExam(examId)
    ElMessage.success('Exam deleted')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Delete failed:', error)
      ElMessage.error('Delete failed')
    }
  }
}

const handleReparseExam = async (examId) => {
  try {
    await examStore.reparseExam(examId)
    ElMessage.success('Reparse started (skipping OCR)')
  } catch (error) {
    console.error('Reparse failed:', error)
    ElMessage.error('Reparse failed')
  }
}


const formatContent = (content, examId) => {
  if (!content) return '';

  try {
      // 1. 预处理图片路径：将 ![alt](images/xxx.jpg) 替换为完整 URL
      // 防止 marked 解析不到本地路径
      let processed = content.replace(/!\[(.*?)\]\((.*?)\)/g, (match, alt, path) => {
         const filename = path.split('/').pop();
         const src = `/api/exams/${examId}/images/${filename}`;
         return `![${alt}](${src})`; 
      });

      // 2. 保护 LaTeX 公式 (防止 Markdown 处理其中的字符如 *, _)
      const latexMatches = [];
      
      // 保护块级公式 $$...$$
      processed = processed.replace(/\$\$([\s\S]+?)\$\$/g, (match, tex) => {
        latexMatches.push({ tex, display: true });
        return `LATEXBLOCK${latexMatches.length - 1}ENDLATEXBLOCK`;
      });
      
      // 保护行内公式 $...$ 
      processed = processed.replace(/\$([^$\n]+?)\$/g, (match, tex) => {
        latexMatches.push({ tex, display: false });
        return `LATEXINLINE${latexMatches.length - 1}ENDLATEXINLINE`;
      });

      // 3. Markdown 解析
      let html = marked.parse(processed);

      // 4. 恢复 LaTeX 并渲染
      // 恢复块级
      html = html.replace(/LATEXBLOCK(\d+)ENDLATEXBLOCK/g, (match, index) => {
          const item = latexMatches[parseInt(index)];
          try {
              return katex.renderToString(item.tex, {
                  displayMode: true,
                  throwOnError: false
              });
          } catch (e) {
              console.error("Katex error:", e);
              return item.tex;
          }
      });
      
      // 恢复行内
      html = html.replace(/LATEXINLINE(\d+)ENDLATEXINLINE/g, (match, index) => {
          const item = latexMatches[parseInt(index)];
          try {
              return katex.renderToString(item.tex, {
                  displayMode: false,
                  throwOnError: false
              });
          } catch (e) {
              return item.tex;
          }
      });
      
      // 5. 额外优化：让图片显示更好看
      // marked 生成的 img 标签没有样式，我们手动加一点
      html = html.replace(/<img /g, '<img style="max-width: 100%; border-radius: 4px; border: 1px solid #eee; margin: 8px 0;" ');

      return html;
  } catch (err) {
      console.error("Format content error:", err);
      return content; // 降级返回原文
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

/* Section */
.resource-section {
  margin-bottom: 24px;
}

.section-header {
  margin-bottom: 16px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.section-desc {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-left: 26px;
}

.section-divider {
  margin: 32px 0;
}

/* Upload Zone */
.upload-section {
  margin-bottom: 20px;
}

.upload-dropzone :deep(.el-upload-dragger) {
  background-color: var(--bg-card);
  border: 2px dashed var(--border-subtle);
  border-radius: 12px;
  padding: 32px 20px;
  transition: all 0.2s;
}

.upload-dropzone :deep(.el-upload-dragger:hover) {
  border-color: var(--color-accent);
  background-color: var(--color-accent-light);
}

.exam-upload :deep(.el-upload-dragger) {
  border-color: var(--border-subtle);
}

.exam-upload :deep(.el-upload-dragger:hover) {
  border-color: var(--text-secondary);
  background-color: var(--bg-page);
}

.dropzone-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

/* Grid - 全局单列列表布局 */
.documents-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.document-card {
  background-color: var(--bg-card);
  border-radius: 12px;
  padding: 12px 20px;
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
  border-color: var(--text-tertiary);
}

/* 移除特定的 exam-card 样式，通用样式已覆盖 */
.exam-card {
  border-left: none;
}

/* 强制 doc-info 横向排列 */
.doc-info {
  flex: 1;
  overflow: hidden;
  display: flex;
  align-items: center;
  gap: 16px;
}

.doc-title {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0; /* 彻底清除边距 */
  line-height: normal; /* 重置行高，让 Flexbox 负责居中 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  display: flex;
  align-items: center; /* 确保文字块内部也垂直居中 */
  height: 100%; /* 占满父容器高度 */
}

.doc-meta {
  display: flex;
  align-items: center;
  gap: 16px; /* 加大一点间距 */
  font-size: 11px;
  color: var(--text-tertiary);
  flex-shrink: 0;
  margin-left: 16px; /* 与标题保持距离 */
  margin-right: 16px; /* 与操作按钮保持距离 */
}



/* 图标样式：极简灰 */
.doc-icon-wrapper {
  width: 44px;
  height: 44px;
  background-color: #F3F4F6; /* 统一浅灰背景 */
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 11px;
  color: #4B5563; /* 深灰文字 */
  border: 1px solid #E5E7EB; /* 微妙的边框 */
}

.exam-icon {
  background-color: #2c2c2c; /* 深色块突显示例 */
  color: #ffffff;
  border: none;
}

/* 年份标签：中性设计 */
.doc-year {
  background-color: #F3F4F6;
  color: #374151;
  padding: 2px 8px;
  border-radius: 12px; /* 更圆润 */
  font-weight: 500;
  font-size: 11px;
  border: 1px solid #E5E7EB;
}

.doc-status {
  display: flex;
  align-items: center;
  gap: 4px;
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
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12px;
  min-width: auto;
  opacity: 1; /* 常驻显示 */
  margin-left: auto; /* 推到最右边 */
}

/* 如果需要 hover 才显示，可以改回 0，但在宽列表模式下常驻更好
.document-card:hover .doc-actions {
  opacity: 1;
}
*/

/* Empty & Loading */
.empty-state {
  padding: 20px 0;
}

.loading-state {
  padding: 20px 0;
}

/* Exam Detail Drawer */
.exam-detail-content {
  padding: 8px;
}

.exam-meta p {
  margin-bottom: 8px;
  font-size: 14px;
}

.questions-tree {
  background: transparent;
}

.questions-tree :deep(.el-tree-node__content) {
  height: auto;
  padding: 8px 0;
  align-items: flex-start; /* 让内容顶对齐 */
}

.custom-tree-node {
  width: 100%;
  padding-right: 12px;
  overflow: hidden;
}

.node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.node-score {
  margin-left: 8px;
}

.node-content {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: normal;
  word-break: break-word; /* 允许自动换行 */
  margin-bottom: 8px;
}

.node-options {
  background-color: #f9fafb;
  padding: 8px;
  border-radius: 4px;
  font-size: 13px;
  color: var(--text-secondary);
}

.option-item {
  margin-bottom: 4px;
}

.option-item:last-child {
  margin-bottom: 0;
}
</style>
