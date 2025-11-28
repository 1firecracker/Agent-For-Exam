<template>
  <div class="home-view">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>系统状态</span>
        </div>
      </template>
      
      <el-space direction="vertical" size="large" style="width: 100%">
        <div>
          <el-text>后端 API 状态：</el-text>
          <el-tag :type="apiStatus === 'connected' ? 'success' : apiStatus === 'error' ? 'danger' : 'info'">
            {{ apiStatus === 'connected' ? '已连接' : apiStatus === 'error' ? '连接失败' : '未知' }}
          </el-tag>
        </div>
        
        <el-button 
          type="primary" 
          @click="checkHealth"
          :loading="loading"
        >
          检查连接
        </el-button>
        
        <div v-if="healthData">
          <el-descriptions title="后端信息" :column="1" border>
            <el-descriptions-item label="状态">{{ healthData.status }}</el-descriptions-item>
            <el-descriptions-item label="版本" v-if="healthData.version">{{ healthData.version }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </el-space>
    </el-card>

    <!-- 阶段5 测试区域 -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>阶段5 功能测试</span>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <!-- 对话管理测试 -->
        <el-tab-pane label="对话管理" name="conversation">
          <el-space direction="vertical" size="large" style="width: 100%">
            <div>
              <el-button type="primary" @click="testCreateConversation" :loading="convStore.loading">
                创建对话（自动编号）
              </el-button>
              <el-button @click="testCreateConversationWithTitle" :loading="convStore.loading">
                创建对话（指定标题）
              </el-button>
              <el-button @click="testLoadConversations" :loading="convStore.loading">
                加载对话列表
              </el-button>
            </div>
            
            <div v-if="convStore.conversationCount > 0">
              <el-text>对话数量: {{ convStore.conversationCount }}</el-text>
              <el-table :data="convStore.conversations" style="width: 100%">
                <el-table-column prop="title" label="标题" />
                <el-table-column prop="file_count" label="文件数" width="100" />
                <el-table-column prop="created_at" label="创建时间" />
                <el-table-column label="操作" width="150">
                  <template #default="scope">
                    <el-button size="small" @click="testSelectConversation(scope.row.conversation_id)">
                      选择
                    </el-button>
                    <el-button size="small" type="danger" @click="testDeleteConversation(scope.row.conversation_id)">
                      删除
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <div v-if="convStore.currentConversation">
              <el-descriptions title="当前对话" :column="1" border>
                <el-descriptions-item label="ID">{{ convStore.currentConversation.conversation_id }}</el-descriptions-item>
                <el-descriptions-item label="标题">{{ convStore.currentConversation.title }}</el-descriptions-item>
                <el-descriptions-item label="文件数">{{ convStore.currentConversation.file_count }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </el-space>
        </el-tab-pane>

        <!-- 文档管理测试 -->
        <el-tab-pane label="文档管理" name="document">
          <el-space direction="vertical" size="large" style="width: 100%">
            <el-alert
              v-if="!convStore.currentConversationId"
              type="warning"
              title="请先选择或创建一个对话"
              :closable="false"
            />
            
            <div v-else>
              <el-text>当前对话: {{ convStore.currentConversation?.title }}</el-text>
              <div style="margin-top: 10px;">
                <el-upload
                  :http-request="handleUpload"
                  :before-upload="handleBeforeUpload"
                  :multiple="true"
                  :limit="20"
                >
                  <el-button type="primary">上传文档</el-button>
                  <template #tip>
                    <div class="el-upload__tip">支持 .pptx 和 .pdf 格式，最大 50MB</div>
                  </template>
                </el-upload>
              </div>

              <el-button 
                @click="testLoadDocuments" 
                :loading="docStore.loading"
                style="margin-top: 10px;"
              >
                加载文档列表
              </el-button>

              <div v-if="docStore.getDocumentsByConversation(convStore.currentConversationId).length > 0" style="margin-top: 10px;">
                <el-table :data="docStore.getDocumentsByConversation(convStore.currentConversationId)" style="width: 100%">
                  <el-table-column prop="filename" label="文件名" />
                  <el-table-column prop="file_size" label="大小" width="120">
                    <template #default="scope">
                      {{ formatFileSize(scope.row.file_size) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="status" label="状态" width="100">
                    <template #default="scope">
                      <el-tag :type="getStatusType(scope.row.status)">
                        {{ scope.row.status }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="120">
                    <template #default="scope">
                      <el-button 
                        size="small" 
                        @click="testGetDocumentStatus(scope.row.file_id)"
                      >
                        状态
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </el-space>
        </el-tab-pane>

        <!-- PPT 查看器测试 -->
        <el-tab-pane label="PPT 查看器" name="ppt">
          <el-space direction="vertical" size="large" style="width: 100%">
            <el-alert
              v-if="!convStore.currentConversationId"
              type="warning"
              title="请先选择或创建一个对话"
              :closable="false"
            />
            
            <div v-else style="height: 600px;">
              <PPTViewer />
            </div>
          </el-space>
        </el-tab-pane>

        <!-- 知识图谱测试 -->
        <el-tab-pane label="知识图谱" name="graph" class="graph-tab-pane">
          <div class="graph-tab-content">
            <el-alert
              v-if="!convStore.currentConversationId"
              type="warning"
              title="请先选择或创建一个对话"
              :closable="false"
              style="margin-bottom: 20px;"
            />
            
            <div v-else class="graph-container">
              <!-- 知识图谱可视化 -->
              <div class="graph-viewer-wrapper">
                <GraphViewer />
              </div>
              
              <!-- 查询功能（可选） -->
              <el-card class="graph-query-card">
                <template #header>图谱查询</template>
                <div style="display: flex; gap: 10px; align-items: center;">
                  <el-input
                    v-model="queryText"
                    placeholder="输入查询问题（例如：什么是人工智能？）"
                    style="flex: 1;"
                    @keyup.enter="testQuery"
                  />
                  <el-button type="primary" @click="testQuery" :loading="graphStore.querying">
                    查询
                  </el-button>
                </div>

                <div v-if="graphStore.queryResult" style="margin-top: 15px;">
                  <el-divider />
                  <div style="white-space: pre-wrap; line-height: 1.6; color: #303133;">
                    {{ graphStore.queryResult.result }}
                  </div>
                </div>
              </el-card>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../services/api'
import { useConversationStore } from '../stores/conversationStore'
import { useDocumentStore } from '../stores/documentStore'
import { useGraphStore } from '../stores/graphStore'
import PPTViewer from '../components/PPTViewer/PPTViewer.vue'
import GraphViewer from '../components/GraphViewer/GraphViewer.vue'

const apiStatus = ref('unknown') // unknown, connected, error
const loading = ref(false)
const healthData = ref(null)

// Stores
const convStore = useConversationStore()
const docStore = useDocumentStore()
const graphStore = useGraphStore()

// 测试相关
const activeTab = ref('conversation')
const queryText = ref('')

// 健康检查
const checkHealth = async () => {
  loading.value = true
  apiStatus.value = 'unknown'
  healthData.value = null
  
  try {
    const response = await api.get('/health')
    apiStatus.value = 'connected'
    healthData.value = response
  } catch (error) {
    console.error('Health check failed:', error)
    apiStatus.value = 'error'
  } finally {
    loading.value = false
  }
}

// 对话管理测试
const testCreateConversation = async () => {
  try {
    const conversation = await convStore.createConversation()
    ElMessage.success(`创建成功: ${conversation.title}`)
    convStore.selectConversation(conversation.conversation_id)
  } catch (error) {
    console.error('Create conversation failed:', error)
  }
}

const testCreateConversationWithTitle = async () => {
  try {
    const title = `测试对话_${Date.now()}`
    const conversation = await convStore.createConversation(title)
    ElMessage.success(`创建成功: ${conversation.title}`)
    convStore.selectConversation(conversation.conversation_id)
  } catch (error) {
    console.error('Create conversation failed:', error)
  }
}

const testLoadConversations = async () => {
  try {
    await convStore.loadConversations()
    ElMessage.success('加载成功')
  } catch (error) {
    console.error('Load conversations failed:', error)
  }
}

const testSelectConversation = (conversationId) => {
  convStore.selectConversation(conversationId)
  ElMessage.success('已选择对话')
  // 切换标签页到文档管理
  activeTab.value = 'document'
}

const testDeleteConversation = async (conversationId) => {
  try {
    await convStore.deleteConversation(conversationId)
    ElMessage.success('删除成功')
  } catch (error) {
    console.error('Delete conversation failed:', error)
  }
}

// 文档管理测试
const testLoadDocuments = async () => {
  if (!convStore.currentConversationId) {
    ElMessage.warning('请先选择对话')
    return
  }
  try {
    await docStore.loadDocuments(convStore.currentConversationId)
    ElMessage.success('加载成功')
  } catch (error) {
    console.error('Load documents failed:', error)
  }
}

const handleBeforeUpload = (file) => {
  const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.presentationml.presentation']
  if (!allowedTypes.includes(file.type)) {
    ElMessage.error('仅支持 .pdf 和 .pptx 格式')
    return false
  }
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 50MB')
    return false
  }
  return true
}

const handleUpload = async (options) => {
  const { file } = options
  try {
    const response = await docStore.uploadDocuments(convStore.currentConversationId || 'new', file)
    ElMessage.success('上传成功')
    // 重新加载文档列表
    if (response.conversation_id) {
      await docStore.loadDocuments(response.conversation_id)
      // 如果自动创建了对话，选择它
      if (response.conversation_id !== convStore.currentConversationId) {
        await convStore.loadConversation(response.conversation_id)
        convStore.selectConversation(response.conversation_id)
      }
    }
  } catch (error) {
    console.error('Upload failed:', error)
  }
}

const testGetDocumentStatus = async (fileId) => {
  if (!convStore.currentConversationId) return
  try {
    const status = await docStore.getDocumentStatus(convStore.currentConversationId, fileId)
    ElMessage.info(`状态: ${status.status}`)
  } catch (error) {
    console.error('Get document status failed:', error)
  }
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const getStatusType = (status) => {
  const statusMap = {
    pending: 'info',
    processing: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return statusMap[status] || 'info'
}

// 知识图谱测试
const testLoadGraph = async () => {
  if (!convStore.currentConversationId) {
    ElMessage.warning('请先选择对话')
    return
  }
  try {
    await graphStore.loadGraph(convStore.currentConversationId)
    ElMessage.success('加载成功')
  } catch (error) {
    console.error('Load graph failed:', error)
  }
}

const testQuery = async () => {
  if (!convStore.currentConversationId) {
    ElMessage.warning('请先选择对话')
    return
  }
  if (!queryText.value.trim()) {
    ElMessage.warning('请输入查询问题')
    return
  }
  try {
    await graphStore.query(convStore.currentConversationId, queryText.value)
    ElMessage.success('查询完成')
  } catch (error) {
    console.error('Query failed:', error)
  }
}

onMounted(() => {
  checkHealth()
  // 自动加载对话列表
  testLoadConversations()
})
</script>

<style scoped>
.home-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 知识图谱标签页样式 */
.graph-tab-pane {
  height: 100%;
}

.graph-container {
  width: 100%;
  height: calc(100vh - 300px);
  min-height: 700px;
  display: flex;
  flex-direction: column;
}

.graph-tab-content {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 700px;
}

.graph-container {
  width: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 700px;
  gap: 20px;
}

.graph-viewer-wrapper {
  flex: 1;
  width: 100%;
  min-height: 600px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.graph-query-card {
  flex-shrink: 0;
  width: 100%;
}

/* 确保el-tabs内容区域填充 */
.graph-tab-pane :deep(.el-tab-pane) {
  height: 100%;
  padding: 0;
}
</style>
