<template>
  <div class="subjects-dashboard">
    <!-- 顶部标题区 -->
    <header class="page-header">
      <div class="header-left">
        <h2 class="page-title">
          <el-icon><Collection /></el-icon>
          Knowledge Bases
        </h2>
        <p class="page-subtitle">Select a subject to manage documents or start a conversation.</p>
      </div>
      <div class="header-right">
        <el-button 
          type="primary" 
          size="large" 
          round
          class="new-subject-btn"
          @click="createNewSubject"
          :loading="convStore.loading"
        >
          <el-icon><Plus /></el-icon>
          New Subject
        </el-button>
      </div>
    </header>

    <!-- 学科列表区域 -->
    <section class="subjects-section">
      <div v-if="convStore.loading && convStore.conversations.length === 0" class="loading-state">
        <el-skeleton :rows="3" animated count="3" class="skeleton-card" />
      </div>

      <div v-else-if="convStore.conversations.length === 0" class="empty-state">
        <el-empty description="No subjects yet. Create one to get started." :image-size="160">
          <el-button type="primary" @click="createNewSubject">Create First Subject</el-button>
        </el-empty>
      </div>

      <div v-else class="subjects-grid">
        <div 
          v-for="conv in convStore.conversations" 
          :key="conv.conversation_id" 
          class="subject-card"
          @click="enterSubject(conv)"
        >
          <div class="card-icon">
            {{ getSubjectIcon(conv.title) }}
          </div>
          
          <div class="card-content">
            <h3 class="subject-title" :title="conv.title">{{ conv.title }}</h3>
            <div class="subject-meta">
              <el-tag size="small" type="info" effect="plain" round>{{ conv.file_count }} Docs</el-tag>
              <span class="date">{{ formatDate(conv.created_at) }}</span>
            </div>
          </div>

          <div class="card-actions">
            <el-button circle size="small" :icon="Delete" @click.stop="handleDelete(conv)" class="delete-btn" />
            <el-icon class="arrow-icon"><ArrowRight /></el-icon>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Collection, Plus, ArrowRight, Delete } from '@element-plus/icons-vue'
import { useConversationStore } from '../modules/chat/store/conversationStore'

const router = useRouter()
const convStore = useConversationStore()

onMounted(async () => {
  await convStore.loadConversations()
})

const createNewSubject = async () => {
  try {
    const { value: title } = await ElMessageBox.prompt('Please enter the subject name', 'New Subject', {
      confirmButtonText: 'Create',
      cancelButtonText: 'Cancel',
      inputPattern: /\S+/,
      inputErrorMessage: 'Name cannot be empty'
    })
    
    if (title) {
      const newConv = await convStore.createConversation(title)
      ElMessage.success('Subject created')
      enterSubject(newConv)
    }
  } catch (e) {
    // Cancelled or error
  }
}

const enterSubject = (conv) => {
  // 设置当前会话
  convStore.selectConversation(conv.conversation_id)
  // 跳转到文档管理页 (也是该 Subject 的首页)
  // 假设路由我们稍后会改为 /subject/:id
  // 目前先暂时跳到 /workspace (文档页)，我们需要确保 DocumentView 能读取 currentConversationId
  // 或者跳转到我们在 Step 2 定义的新路由
  router.push(`/subject/${conv.conversation_id}`)
}

const handleDelete = async (conv) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete "${conv.title}"? This will delete all documents and history.`,
      'Warning',
      {
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel',
        type: 'warning'
      }
    )
    await convStore.deleteConversation(conv.conversation_id)
    ElMessage.success('Deleted')
  } catch (e) {
    // Cancelled
  }
}

const getSubjectIcon = (title) => {
  const firstChar = title ? title.charAt(0).toUpperCase() : 'S'
  return firstChar
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString()
}
</script>

<style scoped>
.subjects-dashboard {
  max-width: 1000px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 40px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.page-title {
  font-family: var(--font-serif);
  font-size: 32px;
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
  font-size: 16px;
}

.new-subject-btn {
  background-color: var(--color-accent);
  border-color: var(--color-accent);
}

.new-subject-btn:hover {
  background-color: var(--color-accent-hover);
  border-color: var(--color-accent-hover);
}

/* Grid */
.subjects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 24px;
}

.subject-card {
  background-color: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 20px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.subject-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-float);
  border-color: var(--color-accent);
}

.card-icon {
  width: 56px;
  height: 56px;
  background-color: var(--color-accent-light);
  color: var(--color-accent);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 700;
  flex-shrink: 0;
}

.card-content {
  flex: 1;
  overflow: hidden;
}

.subject-title {
  font-family: var(--font-sans);
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.subject-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--text-tertiary);
}

.card-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  opacity: 0.5;
  transition: opacity 0.2s;
}

.subject-card:hover .card-actions {
  opacity: 1;
}

.arrow-icon {
  font-size: 20px;
  color: var(--text-tertiary);
}

.delete-btn {
  color: var(--text-tertiary);
}

.delete-btn:hover {
  color: #DC2626;
  background-color: #FEF2F2;
  border-color: #FECACA;
}
</style>
