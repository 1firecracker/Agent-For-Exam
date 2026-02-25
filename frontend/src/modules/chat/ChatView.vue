<template>
  <div class="chat-workspace">
    <!-- 对话区域（全屏） -->
    <div class="chat-main" :style="{ marginRight: isPanelCollapsed ? '0' : `${sidebarWidth}px` }">
      <!-- 消息列表区域 -->
      <div class="messages-container" ref="messagesContainer" @click="handleReferenceClick">
        <div v-if="messages.length === 0" class="empty-state">
          <div class="logo-placeholder">
            <span class="logo-icon">✨</span>
          </div>
          <h2 class="welcome-text">How can I help you with these documents?</h2>
        </div>

        <div v-else class="message-list">
          <div 
            v-for="(msg, index) in messages" 
            :key="index" 
            class="message-row"
            :class="msg.role"
          >
            <div class="avatar">
              {{ msg.role === 'user' ? 'U' : 'A' }}
            </div>
            <div class="message-content">
              <div class="sender-name">{{ msg.role === 'user' ? 'You' : 'Agent' }}</div>
              
              <!-- 用户消息 -->
              <template v-if="msg.role === 'user'">
                <div class="user-message-wrapper">
                  <div v-if="editingMessageIndex !== index" class="bubble user-bubble">
                {{ msg.content }}
                    <button 
                      class="edit-btn" 
                      @click="startEdit(index, msg.content)"
                      :disabled="isLoading"
                      title="编辑消息"
                    >
                      <el-icon><Edit /></el-icon>
                    </button>
                  </div>
                  <div v-else class="edit-wrapper">
                    <textarea
                      v-model="editingContent"
                      class="edit-input"
                      rows="3"
                      ref="editTextareaRef"
                    ></textarea>
                    <div class="edit-actions">
                      <button 
                        class="edit-save-btn" 
                        @click="handleSaveEdit(index)"
                        :disabled="!editingContent.trim()"
                      >
                        <el-icon><Check /></el-icon>
                        保存并重新生成
                      </button>
                      <button 
                        class="edit-cancel-btn" 
                        @click="cancelEdit"
                      >
                        <el-icon><Close /></el-icon>
                        取消
                      </button>
                    </div>
                  </div>
              </div>
              </template>
              
              <!-- AI 回复 -->
              <template v-else>
                <!-- Think 内容折叠栏（在顶部） -->
                <div v-if="hasThinkContent(msg.content)" class="think-section">
                  <el-collapse v-model="thinkCollapseStates">
                    <el-collapse-item :name="index" :title="'Thinking Process'" class="think-collapse">
                      <div class="think-content" v-html="formatThinkContent(msg.content)"></div>
                    </el-collapse-item>
                  </el-collapse>
            </div>
                
                <!-- 如果有 streamItems，按顺序显示工具调用和文本 -->
                <template v-if="msg.streamItems && msg.streamItems.length > 0">
                  <template v-for="(item, itemIndex) in msg.streamItems" :key="itemIndex">
                    <!-- 工具调用 -->
                    <div v-if="item.type === 'tool_call' && item.toolName && item.toolName.trim()" class="tool-calls-section">
                      <ToolCallInline
                        :tool-name="item.toolName"
                        :tool-arguments="item.arguments"
                        :result="item.result"
                        :error-message="item.errorMessage"
                        :status="item.status"
                        :progress="item.progress"
                      />
          </div>
                    <!-- 文本内容 -->
                    <div v-else-if="item.type === 'text'" class="bubble message-text">
                      <span v-html="formatMessageWithWarning(item.content)"></span>
                    </div>
                  </template>
                </template>
                <!-- 如果没有 streamItems，使用旧的显示方式（向后兼容） -->
                <template v-else>
                  <!-- 工具调用 -->
                  <div v-if="msg.toolCalls && msg.toolCalls.length > 0 && msg.toolCalls.some(tc => tc.toolName && tc.toolName.trim())" class="tool-calls-section">
                    <ToolCallInline
                      v-for="(toolCall, toolIndex) in msg.toolCalls.filter(tc => tc.toolName && tc.toolName.trim())"
                      :key="toolIndex"
                      :tool-name="toolCall.toolName"
                      :tool-arguments="toolCall.arguments"
                      :result="toolCall.result"
                      :error-message="toolCall.errorMessage"
                      :status="toolCall.status"
                      :progress="toolCall.progress"
                    />
                  </div>
                  
                  <div class="bubble message-text" v-html="formatMessageWithWarning(msg.content)"></div>
                </template>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部输入框 -->
      <div class="input-area-wrapper">
        <div class="input-box">
          <textarea 
            v-model="inputMessage"
            class="chat-input"
            placeholder="Ask anything about your documents..."
            @keydown.enter.prevent="handleSend"
            rows="1"
            ref="textareaRef"
          ></textarea>
          <button 
            v-if="!isLoading"
            class="send-btn" 
            :disabled="!inputMessage.trim() || isLoading || editingMessageIndex !== null"
            @click="handleSend"
          >
            <el-icon><Top /></el-icon>
          </button>
          <button 
            v-else
            class="stop-btn" 
            @click="handleStop"
            title="停止生成"
          >
            <span class="stop-icon"></span>
          </button>
        </div>
        <div class="input-footer">
          Agent can make mistakes. Please verify important information.
        </div>
      </div>
    </div>

    <!-- 右侧可折叠侧边栏（集成在对话区域内） -->
    <div 
      class="sidebar-panel" 
      :class="{ collapsed: isPanelCollapsed }"
      :style="{ width: isPanelCollapsed ? '0' : `${sidebarWidth}px` }"
    >
      <!-- 拖动调整大小的分隔条 -->
      <div 
        class="sidebar-resizer"
        v-show="!isPanelCollapsed"
        @mousedown="handleResizeStart"
        :title="'拖动调整宽度'"
      ></div>
      
      <div class="sidebar-toggle" @click="isPanelCollapsed = !isPanelCollapsed" :title="isPanelCollapsed ? '展开侧边栏' : '折叠侧边栏'">
        <el-icon><component :is="isPanelCollapsed ? ArrowLeft : ArrowRight" /></el-icon>
      </div>

      <div class="sidebar-content" v-show="!isPanelCollapsed">
        <el-tabs v-model="activeTab" class="sidebar-tabs">
          <!-- 试题分析对话：习题解析进度 Tab（默认） -->
          <el-tab-pane v-if="isExamAnalysisConversation" label="习题解析进度" name="analysis">
            <div class="tab-content-wrapper">
              <ExamAnalysisProgress v-if="conversationId" />
            </div>
          </el-tab-pane>

          <!-- 普通对话：思维导图 Tab -->
          <el-tab-pane v-if="!isExamAnalysisConversation" label="Mind Map" name="mindmap">
            <div class="tab-content-wrapper">
               <MindMapViewer v-if="conversationId" />
            </div>
          </el-tab-pane>

          <!-- 文档 Tab -->
          <el-tab-pane label="Documents" name="documents">
            <div class="docs-panel">
              <!-- PPT 查看器 -->
              <PPTViewer 
                v-if="conversationId" 
                ref="pptViewerRef"
                :default-file-id="selectedDocumentId"
              />
              <el-empty
                v-else
                description="请先选择或创建一个对话"
                :image-size="120"
              />
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>

    <!-- 知识图谱弹窗 -->
    <el-dialog
      v-model="showGraphModal"
      title="Knowledge Graph"
      width="90%"
      top="5vh"
      class="graph-modal"
      :destroy-on-close="true" 
    >
      <div class="modal-graph-container">
        <GraphViewer />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import { Top, ArrowRight, ArrowLeft, Share, Edit, Close, Check } from '@element-plus/icons-vue'
import { marked } from 'marked'
import katex from 'katex'
import { useConversationStore } from './store/conversationStore'
import { useDocumentStore } from '../documents/store/documentStore'
import { useChatStore } from './store/chatStore'
import GraphViewer from '../graph/components/GraphViewer.vue'
import MindMapViewer from '../mindmap/components/MindMapViewer.vue'
import PPTViewer from '../documents/components/PPTViewer/PPTViewer.vue'
import ExamAnalysisProgress from './components/ExamAnalysisProgress.vue'
import ToolCallInline from './components/ToolCallInline.vue'
import { api, BASE_URL } from '../../services/api'
import chatService from './services/chatService'

// 配置 marked 选项
marked.setOptions({
  breaks: true, // 支持换行
  gfm: true,    // 支持 GitHub 风格 Markdown
})

const route = useRoute()
const subjectId = computed(() => route.params.subjectId || null)
const conversationId = computed(() => route.params.conversationId || route.params.id)
const convStore = useConversationStore()
const docStore = useDocumentStore()
const chatStore = useChatStore()

const inputMessage = ref('')
const isLoading = ref(false)
const messagesContainer = ref(null)
const textareaRef = ref(null)
const editTextareaRef = ref(null)

// 对话打断相关
const abortController = ref(null)

// 编辑相关
const editingMessageIndex = ref(null)
const editingContent = ref('')

// 面板状态
const isPanelCollapsed = ref(false)
const activeTab = ref('mindmap')
const showGraphModal = ref(false)

// 试题分析专属对话：右侧默认显示「习题解析进度」
const isExamAnalysisConversation = computed(() => convStore.currentConversation?.conversation_type === 'exam_analysis')

watch(isExamAnalysisConversation, (isExam) => {
  activeTab.value = isExam ? 'analysis' : 'mindmap'
}, { immediate: true })

// 侧边栏宽度（可拖动调整）
// 默认宽度为对话空间的60%
const getDefaultSidebarWidth = () => {
  const leftSidebarWidth = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width')) || 260
  const chatSpaceWidth = window.innerWidth - leftSidebarWidth
  return Math.floor(chatSpaceWidth * 0.6)
}
const sidebarWidth = ref(getDefaultSidebarWidth())
const isResizing = ref(false)
const minSidebarWidth = 300
const maxSidebarWidth = 800

// Think 内容折叠状态
const thinkCollapseStates = ref([])

// 消息数据
const messages = ref([])

// 当前选中的文档ID（用于 PPT 查看器）
const selectedDocumentId = ref(null)

// PPT 查看器引用
const pptViewerRef = ref(null)

// 获取当前对话的文档
const currentDocuments = computed(() => {
  if (!conversationId.value) return []
  return docStore.getDocumentsByConversation(conversationId.value) || []
})

// 监听文档列表变化，自动选择第一个支持的文档（PPTX/PDF）
watch(currentDocuments, (docs) => {
  if (docs.length > 0 && !selectedDocumentId.value) {
    // 优先选择 PPTX，其次 PDF
    const pptxDoc = docs.find(doc => doc.file_extension === 'pptx')
    const pdfDoc = docs.find(doc => doc.file_extension === 'pdf')
    selectedDocumentId.value = (pptxDoc || pdfDoc)?.file_id || null
    console.log('📄 自动选择文档:', selectedDocumentId.value)
  }
}, { immediate: true })

// 自动调整输入框高度
watch(inputMessage, () => {
  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto'
      textareaRef.value.style.height = textareaRef.value.scrollHeight + 'px'
    }
  })
})

// 节流滚动，避免频繁更新导致卡顿
let scrollTimer = null
const scrollToBottom = () => {
  if (scrollTimer) return // 如果已有待执行的滚动，跳过
  
  scrollTimer = setTimeout(() => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
    scrollTimer = null
  }, 50) // 50ms 节流
}

// 加载历史消息
const loadMessages = async () => {
  if (!conversationId.value) return
  try {
    const res = await api.get(`/api/conversations/${conversationId.value}/messages`)
    
    if (res.messages) {
      // 过滤掉 tool 角色的消息，这些消息不应该显示给用户
      // tool 消息包含大量的工具执行结果数据，会导致性能问题
      let filteredMessages = res.messages
        .filter(m => m.role !== 'tool') // 过滤 tool 消息
        .map(m => ({
          role: m.role === 'human' ? 'user' : m.role, // 兼容后端可能返回 human
          content: m.content || '',
          streamItems: m.streamItems || null, // 保留 streamItems（工具调用信息在这里）
          toolCalls: m.toolCalls || null // 保留 toolCalls（向后兼容）
        }))
      
      // 合并连续的 assistant 消息（一条有 tool_calls，一条有 content）
      const mergedMessages = []
      for (let i = 0; i < filteredMessages.length; i++) {
        const current = filteredMessages[i]
        const next = filteredMessages[i + 1]
        
        // 如果当前是 assistant 消息，且只有 tool_calls 没有 content，下一条也是 assistant 且有 content
        if (current.role === 'assistant' && 
            next && next.role === 'assistant' &&
            (!current.content || current.content.trim() === '') &&
            current.toolCalls && current.toolCalls.length > 0 &&
            next.content && next.content.trim() !== '') {
          // 合并两条消息
          const merged = {
            role: 'assistant',
            content: next.content,
            streamItems: next.streamItems || current.streamItems || null,
            toolCalls: current.toolCalls || next.toolCalls || null
          }
          mergedMessages.push(merged)
          i++ // 跳过下一条消息，因为已经合并了
        } else {
          mergedMessages.push(current)
        }
      }
      
      messages.value = mergedMessages
      
      scrollToBottom()
    }
  } catch (e) {
    console.error('Failed to load messages:', e)
  }
}

const handleSend = async () => {
  if (!inputMessage.value.trim() || isLoading.value || editingMessageIndex.value !== null) return

  const content = inputMessage.value.trim()
  inputMessage.value = ''
  
  if (textareaRef.value) textareaRef.value.style.height = 'auto'

  // 1. 添加用户消息
  messages.value.push({
    role: 'user',
    content: content
  })
  scrollToBottom()

  isLoading.value = true
  
  // 创建 AbortController
  abortController.value = new AbortController()

  // 2. 准备 AI 消息占位符
  const aiMessageIndex = messages.value.length
  messages.value.push({
    role: 'assistant',
    content: '', // 初始为空，等待流式填充
    streamItems: [] // 流式输出项（工具调用和文本的混合顺序）
  })
  // 获取响应式的 streamItems 引用
  const streamItems = messages.value[aiMessageIndex].streamItems

  try {
    // 3. 发起流式请求
    const response = await fetch(`${BASE_URL}/api/conversations/${conversationId.value}/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: content,
        mode: 'agent' // 使用 agent 模式以支持工具调用
      }),
      signal: abortController.value.signal
    })

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    
    // 处理单行数据的函数
    const processLine = (line) => {
      if (!line.trim()) return
      
      try {
        const data = JSON.parse(line)
        
        // 处理工具调用
        if (data.tool_call) {
          const toolCall = data.tool_call
          let argumentsObj = {}
          try {
            const argsStr = toolCall.function?.arguments || '{}'
            argumentsObj = typeof argsStr === 'string' ? JSON.parse(argsStr) : argsStr
          } catch (e) {
            console.warn('解析工具调用参数失败:', e)
            argumentsObj = {}
          }
          
          const toolCallItem = {
            type: 'tool_call',
            toolName: toolCall.function?.name || '',
            arguments: argumentsObj,
            result: null,
            errorMessage: null,
            timestamp: Date.now(),
            status: 'pending'
          }
          
          // 直接操作响应式数组，确保 Vue 能检测到变化
          streamItems.push(toolCallItem)
          // 使用 nextTick 确保 DOM 更新
          nextTick(() => {
            scrollToBottom()
          })
        }
        // 处理工具执行结果
        else if (data.tool_result) {
          const toolResult = data.tool_result
          const result = toolResult.result || {}
          
          // 更新 streamItems 中对应的工具调用（从后往前找）
          let toolCallIndex = -1
          for (let i = streamItems.length - 1; i >= 0; i--) {
            if (streamItems[i].type === 'tool_call' && 
                streamItems[i].toolName === toolResult.tool_name && 
                !streamItems[i].result) {
              toolCallIndex = i
              break
            }
          }
          
          if (toolCallIndex !== -1) {
            // 直接修改响应式数组元素，Vue 会自动检测到变化
            streamItems[toolCallIndex].arguments = toolResult.arguments || {}
            streamItems[toolCallIndex].result = result
            streamItems[toolCallIndex].status = result.status === 'success' ? 'success' : (result.status === 'error' ? 'error' : 'pending')
            // 使用 nextTick 确保 DOM 更新
            nextTick(() => {
              scrollToBottom()
            })
          }
        }
        // 处理工具执行进度
        else if (data.tool_progress) {
          const toolProgress = data.tool_progress
          // 找到对应的工具调用
          let toolCallIndex = -1
          for (let i = streamItems.length - 1; i >= 0; i--) {
            if (streamItems[i].type === 'tool_call' && 
                streamItems[i].toolName === toolProgress.tool_name) {
              toolCallIndex = i
              break
            }
          }
          
          if (toolCallIndex !== -1) {
            // 更新进度信息
            streamItems[toolCallIndex].progress = {
              current: toolProgress.progress.current,
              total: toolProgress.progress.total,
              message: toolProgress.progress.message,
              percentage: toolProgress.progress.percentage || Math.round((toolProgress.progress.current / toolProgress.progress.total) * 100)
            }
            // 使用 nextTick 确保 DOM 更新
            nextTick(() => {
              scrollToBottom()
            })
          }
        }
        // 处理工具执行错误
        else if (data.tool_error) {
          const toolError = data.tool_error
          let toolCallIndex = -1
          for (let i = streamItems.length - 1; i >= 0; i--) {
            if (streamItems[i].type === 'tool_call' && 
                streamItems[i].toolName === toolError.tool_name && 
                !streamItems[i].result) {
              toolCallIndex = i
              break
            }
          }
          
          if (toolCallIndex !== -1) {
            // 直接修改响应式数组元素，Vue 会自动检测到变化
            streamItems[toolCallIndex].errorMessage = toolError.message || '工具执行失败'
            streamItems[toolCallIndex].status = 'error'
            // 清除进度信息（如果有）
            streamItems[toolCallIndex].progress = null
            // 使用 nextTick 确保 DOM 更新
            nextTick(() => {
              scrollToBottom()
            })
          }
        }
        // 处理思维脑图内容
        else if (data.mindmap_content) {
          import('../mindmap/store/mindmapStore').then(({ useMindMapStore }) => {
            const mindmapStore = useMindMapStore()
            mindmapStore.mindmapContent = data.mindmap_content
          })
        }
        // 处理正常响应 - 立即更新，实现逐字符显示
        else if (data.response) {
          // 追加到最后一个文本项或创建新项
          const lastItem = streamItems[streamItems.length - 1]
          if (lastItem && lastItem.type === 'text') {
            lastItem.content += data.response
          } else {
            streamItems.push({
              type: 'text',
              content: data.response
            })
          }
          // 同时更新 content 字段（向后兼容）
          messages.value[aiMessageIndex].content += data.response
          // 使用 nextTick 确保 DOM 更新
          nextTick(() => {
            scrollToBottom()
          })
        }
        // 处理警告
        else if (data.warning) {
          console.warn('Warning:', data.warning)
        }
        // 处理错误
        else if (data.error) {
          const errorMsg = data.error
          const errorHtml = `<span class="error-inline">⚠ ${errorMsg}</span>`
          const lastItem = streamItems[streamItems.length - 1]
          if (lastItem && lastItem.type === 'text') {
            lastItem.content += `\n[Error: ${errorMsg}]`
          } else {
            streamItems.push({
              type: 'text',
              content: `[Error: ${errorMsg}]`
            })
          }
          messages.value[aiMessageIndex].content += `\n[Error: ${errorMsg}]`
          // 使用 nextTick 确保 DOM 更新
          nextTick(() => {
            scrollToBottom()
          })
        }
      } catch (e) {
        console.warn('JSON parse error:', e, line)
      }
    }

    // 异步批处理队列，避免阻塞主线程
    const pendingLines = []
    let isProcessing = false
    
    // 异步处理队列中的行（分批处理，避免阻塞）
    const processQueue = () => {
      if (isProcessing || pendingLines.length === 0) return
      
      isProcessing = true
      
      // 每次处理最多 5 行，然后让出控制权给浏览器更新 UI
      const batchSize = 5
      const batch = pendingLines.splice(0, Math.min(batchSize, pendingLines.length))
      
      // 同步处理当前批次
      for (const line of batch) {
        processLine(line)
      }
      
      isProcessing = false
      
      // 如果还有待处理的行，使用微任务继续处理（让浏览器有机会更新 UI）
      if (pendingLines.length > 0) {
        // 使用 Promise.resolve() 创建微任务，比 setTimeout 更快
        Promise.resolve().then(processQueue)
      }
    }
    
    // 添加行到处理队列
    const enqueueLine = (line) => {
      if (line.trim()) {
        pendingLines.push(line)
        // 如果当前没有在处理，立即开始处理
        if (!isProcessing) {
          processQueue()
        }
      }
    }

    while (true) {
      if (abortController.value && abortController.value.signal.aborted) {
        reader.cancel()
        break
      }
      
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      
      // 处理完整的行 - 添加到异步处理队列
      buffer = lines.pop() || '' // 最后一行可能不完整，留到下一次

      // 将完整的行添加到处理队列，异步批处理避免阻塞主线程
      for (const line of lines) {
        enqueueLine(line)
      }
    }
    
    // 处理缓冲区中剩余的不完整行
    if (buffer.trim()) {
      enqueueLine(buffer)
    }
    
    // 等待所有队列中的行处理完成（最多等待 1 秒）
    const maxWaitTime = 1000
    const startTime = Date.now()
    while ((pendingLines.length > 0 || isProcessing) && (Date.now() - startTime < maxWaitTime)) {
      await new Promise(resolve => setTimeout(resolve, 10))
    }
    
    // streamItems 已经是响应式数组的引用，无需重新赋值
    
    // 从 streamItems 中提取文本内容和工具调用
    let fullContent = ''
    const toolCallsFromStream = []
    
    // 从 streamItems 中提取内容
    for (const item of streamItems) {
      if (item.type === 'text') {
        fullContent += item.content
      } else if (item.type === 'tool_call') {
        toolCallsFromStream.push({
          toolName: item.toolName,
          arguments: item.arguments,
          result: item.result,
          errorMessage: item.errorMessage,
          timestamp: item.timestamp,
          status: item.status
        })
      }
    }
    
    // 如果没有 streamItems 或 streamItems 中没有文本，使用 content 字段（向后兼容）
    if (!fullContent && messages.value[aiMessageIndex].content) {
      fullContent = messages.value[aiMessageIndex].content
    }
    
    const finalToolCalls = toolCallsFromStream.length > 0 ? toolCallsFromStream : null
    
    // 保存消息到后端（包含工具调用信息和 streamItems）
    if (fullContent || finalToolCalls) {
      try {
        await chatStore.saveMessage(
          conversationId.value,
          content, // 用户查询
          fullContent, // AI 回复
          finalToolCalls, // 工具调用
          streamItems.length > 0 ? [...streamItems] : null // streamItems
        )
        console.log('✅ 消息已保存到后端')
  } catch (error) {
        console.error('❌ 保存消息失败:', error)
        // 保存失败不影响用户体验，只记录错误
      }
    }
    
  } catch (error) {
    // 如果是用户主动打断，不显示错误提示，保留已接收内容
    if (error.name === 'AbortError') {
      // 保留已接收的部分内容，不显示错误
      console.log('用户中断了生成')
    } else {
      // 其他错误，显示错误信息
    const errorMsg = `[Error: ${error.message}]`
    const lastItem = streamItems[streamItems.length - 1]
    if (lastItem && lastItem.type === 'text') {
      lastItem.content += `\n${errorMsg}`
    } else {
      streamItems.push({
        type: 'text',
        content: errorMsg
      })
    }
    messages.value[aiMessageIndex].content += `\n${errorMsg}`
    
    // 即使出错也尝试保存消息
    try {
      await chatStore.saveMessage(
        conversationId.value,
        content,
        messages.value[aiMessageIndex].content,
        null,
        streamItems.length > 0 ? [...streamItems] : null
      )
    } catch (saveError) {
      console.error('❌ 保存错误消息失败:', saveError)
      }
    }
  } finally {
    isLoading.value = false
    abortController.value = null
    scrollToBottom()
  }
}

// 停止生成
const handleStop = () => {
  if (abortController.value) {
    abortController.value.abort()
    isLoading.value = false
  }
}

// 开始编辑
const startEdit = (index, content) => {
  editingMessageIndex.value = index
  editingContent.value = content
  nextTick(() => {
    if (editTextareaRef.value) {
      editTextareaRef.value.focus()
    }
  })
}

// 取消编辑
const cancelEdit = () => {
  editingMessageIndex.value = null
  editingContent.value = ''
}

// 保存编辑并重新生成
const handleSaveEdit = async (index) => {
  if (!editingContent.value.trim()) return
  
  const newContent = editingContent.value.trim()
  
  // 获取原始消息列表（包含 tool 消息）以找到正确的索引
  const originalMessages = await api.get(`/api/conversations/${conversationId.value}/messages`)
  
  if (!originalMessages.messages) {
    console.error('无法获取原始消息列表')
    return
  }
  
  // 找到被编辑的用户消息在原始列表中的索引
  // 前端 messages.value 中索引为 index 的用户消息
  const editedMessage = messages.value[index]
  
  if (!editedMessage || editedMessage.role !== 'user') {
    console.error('无效的编辑索引')
    return
  }
  
  // 在原始消息列表中找到对应的用户消息
  // 需要模拟前端的过滤和合并逻辑，确保索引匹配正确
  let originalIndex = -1
  const editedContentNormalized = editedMessage.content.trim()
  
  // 模拟前端的过滤和合并逻辑，构建前端索引到原始索引的映射
  // 步骤1：过滤掉 tool 消息，并记录每个过滤后消息对应的原始索引
  const filteredWithIndex = []
  for (let i = 0; i < originalMessages.messages.length; i++) {
    if (originalMessages.messages[i].role !== 'tool') {
      filteredWithIndex.push({
        msg: originalMessages.messages[i],
        originalIndex: i,
        role: originalMessages.messages[i].role === 'human' ? 'user' : originalMessages.messages[i].role
      })
    }
  }
  
  // 步骤2：模拟合并逻辑，构建前端索引映射
  const frontendToOriginalMap = []
  for (let i = 0; i < filteredWithIndex.length; i++) {
    const current = filteredWithIndex[i]
    const next = filteredWithIndex[i + 1]
    
    // 检查是否需要合并（与 loadMessages 中的逻辑一致）
    if (current.role === 'assistant' && 
        next && next.role === 'assistant' &&
        (!current.msg.content || current.msg.content.trim() === '') &&
        current.msg.toolCalls && current.msg.toolCalls.length > 0 &&
        next.msg.content && next.msg.content.trim() !== '') {
      // 合并情况：使用第二条消息的原始索引（因为内容在第二条）
      frontendToOriginalMap.push(next.originalIndex)
      i++ // 跳过下一条
    } else {
      // 非合并情况：直接使用当前消息的原始索引
      frontendToOriginalMap.push(current.originalIndex)
    }
  }
  
  // 步骤3：使用映射表查找原始索引
  if (frontendToOriginalMap[index] !== undefined) {
    const mappedIndex = frontendToOriginalMap[index]
    const originalMsg = originalMessages.messages[mappedIndex]
    
    // 验证：确保是用户消息
    if (originalMsg && (originalMsg.role === 'user' || originalMsg.role === 'human')) {
      originalIndex = mappedIndex
    }
  }
  
  // 如果映射失败，回退到简单匹配（向后兼容）
  if (originalIndex === -1) {
    let filteredCount = 0
    for (let i = 0; i < originalMessages.messages.length; i++) {
      const msg = originalMessages.messages[i]
      if (msg.role === 'tool') {
        continue
      }
      if (filteredCount === index && (msg.role === 'user' || msg.role === 'human')) {
        originalIndex = i
        break
      }
      if (msg.role !== 'tool') {
        filteredCount++
      }
    }
  }
  
  if (originalIndex === -1) {
    console.error('无法找到原始消息索引')
    return
  }
  
  // 调用后端重置历史，保留该索引之前的所有消息
  await chatService.resetHistory(conversationId.value, originalIndex)
  
  // 前端截断消息数组
  messages.value = messages.value.slice(0, index)
  
  // 重置编辑状态
  editingMessageIndex.value = null
  editingContent.value = ''
  
  // 将新内容填入输入框
  inputMessage.value = newContent
  
  // 自动触发发送
  nextTick(() => {
    handleSend()
  })
}

// 初始化加载函数
const initializeConversation = async () => {
  const currentConvId = conversationId.value
  if (!currentConvId) return
  
  console.log('🚀 Initializing conversation:', currentConvId)
  
  // 确保对话被加载
  if (!convStore.currentConversationId || convStore.currentConversationId !== currentConvId) {
    console.log('🔄 Loading conversation details...')
    await convStore.loadConversation(currentConvId)
    convStore.selectConversation(currentConvId)
  }
  
  // 加载文档（使用 subjectId 优先）
  console.log('📂 Loading documents...')
  try {
    if (subjectId.value) {
      // 优先使用 subjectId 加载文档
      await docStore.loadDocumentsForSubject(subjectId.value)
      const docs = docStore.getDocumentsBySubject(subjectId.value)
      console.log('✅ Documents loaded (by subject):', docs)
    
    // 自动选择第一个支持的文档（PPTX 或 PDF）
    if (docs && docs.length > 0) {
      const pptxDoc = docs.find(doc => doc.file_extension === 'pptx')
      const pdfDoc = docs.find(doc => doc.file_extension === 'pdf')
      selectedDocumentId.value = (pptxDoc || pdfDoc)?.file_id || null
      console.log('📄 自动选择文档:', selectedDocumentId.value)
      }
    } else {
      // 回退到旧的 conversationId 方式
      await docStore.loadDocuments(currentConvId)
      const docs = docStore.getDocumentsByConversation(currentConvId)
      console.log('✅ Documents loaded (by conversation):', docs)
      
      if (docs && docs.length > 0) {
        const pptxDoc = docs.find(doc => doc.file_extension === 'pptx')
        const pdfDoc = docs.find(doc => doc.file_extension === 'pdf')
        selectedDocumentId.value = (pptxDoc || pdfDoc)?.file_id || null
        console.log('📄 自动选择文档:', selectedDocumentId.value)
      }
    }
  } catch (e) {
    console.error('❌ Failed to load documents:', e)
  }

  // 加载历史消息
  console.log('💬 Loading messages...')
  await loadMessages()
}

onMounted(async () => {
  // 初始化侧边栏宽度为对话空间的60%
  const leftSidebarWidth = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width')) || 260
  const chatSpaceWidth = window.innerWidth - leftSidebarWidth
  sidebarWidth.value = Math.floor(chatSpaceWidth * 0.6)
  
  await initializeConversation()
})

// 监听路由变化，当 conversationId 改变时重新加载
watch(() => conversationId.value, async (newConvId, oldConvId) => {
  if (newConvId && newConvId !== oldConvId) {
    console.log('🔄 Conversation changed:', oldConvId, '->', newConvId)
    // 清空当前消息
    messages.value = []
    // 重新初始化对话
    await initializeConversation()
  }
}, { immediate: false })

// 拖动调整侧边栏宽度
const handleResizeStart = (e) => {
  e.preventDefault()
  isResizing.value = true
  
  const startX = e.clientX
  const startWidth = sidebarWidth.value
  
  const handleMouseMove = (e) => {
    if (!isResizing.value) return
    
    const diff = startX - e.clientX // 向右拖动时 diff 为正
    let newWidth = startWidth + diff
    
    // 限制宽度范围
    newWidth = Math.max(minSidebarWidth, Math.min(maxSidebarWidth, newWidth))
    sidebarWidth.value = newWidth
  }
  
  const handleMouseUp = () => {
    isResizing.value = false
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
  }
  
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
}

// 检查是否有 think 内容
const hasThinkContent = (text) => {
  if (!text) return false
  return /<(?:think|redacted_reasoning)>/i.test(text)
}

// 提取并格式化 think 内容
const formatThinkContent = (text) => {
  if (!text) return ''
  
  let thinkMatch = text.match(/<(?:think|redacted_reasoning)>([\s\S]*?)<\/(?:think|redacted_reasoning)>/i)
  
  if (!thinkMatch) {
    const openTagMatch = text.match(/<(?:think|redacted_reasoning)>([\s\S]*)$/i)
    if (openTagMatch) {
      thinkMatch = openTagMatch
    } else {
      return ''
    }
  }
  
  let thinkText = thinkMatch[1] || ''
  return formatEnhancedMarkdown(thinkText)
}

// 从 References 部分提取编号到文档信息的映射
const extractReferenceMap = (text) => {
  const refMap = new Map()
  if (!text) return refMap
  
  // 查找 References 部分
  const refSectionMatch = text.match(/##\s+References\s*\n([\s\S]*?)(?=\n##|$)/i)
  if (!refSectionMatch) return refMap
  
  const refContent = refSectionMatch[1]
  
  // 匹配 [1] ... [[file_id|page]]，中间允许出现 [文档] / [知识图谱] 等任意内容
  const refItemPattern = /\[(\d+)\][\s\S]*?\[\[([^|\]]+)\|(\d+)\]\]/g
  let match
  while ((match = refItemPattern.exec(refContent)) !== null) {
    const refNum = parseInt(match[1])
    const fileId = match[2]
    const page = parseInt(match[3])
    refMap.set(refNum, { fileId, page })
  }
  
  return refMap
}

// 从正文提取 [[file_id|page]]（当没有 References 段时用于兜底编号）
const extractInlineRefList = (text) => {
  const refs = []
  if (!text) return refs

  const pattern = /\[\[([^|\]]+)\|([0-9]+)\]\]/g
  let match
  while ((match = pattern.exec(text)) !== null) {
    refs.push({ fileId: match[1], page: parseInt(match[2]) })
  }
  return refs
}

// 解析引用标记并转换为可点击链接
const parseReferences = (html, originalText = '') => {
  if (!html) return html
  
  // 从原始文本中提取引用映射（编号 -> { fileId, page }）
  const refMap = extractReferenceMap(originalText)
  
  // 情况 A：存在 References 段 -> 以 References 的编号映射为准
  if (refMap.size > 0) {
    // 先移除原始的 [[file_id|page]] 标记（作为隐藏元数据，不直接展示给用户）
    let result = html.replace(/\[\[([^|\]]+)\|([0-9]+)\]\]/g, '')

    // 再处理 [1]、[2] 等编号格式（如果 References 中有对应的文档信息）
    result = result.replace(/\[(\d+)\]/g, (match, refNum) => {
      const refInfo = refMap.get(parseInt(refNum))
      if (refInfo) {
        return `<span class="reference-link clickable" data-file-id="${refInfo.fileId}" data-page="${refInfo.page}">[${refNum}]</span>`
      }
      // 如果没有对应的文档信息，保持原样但添加样式类（不可点击）
      return `<span class="reference-number">[${refNum}]</span>`
    })

    return result
  }

  // 情况 B：没有 References 段 -> 将正文里的 [[file_id|page]] 直接替换成可点击 [1][2]...
  const inlineRefs = extractInlineRefList(originalText)
  if (!inlineRefs.length) return html

  let idx = 0
  return html.replace(/\[\[([^|\]]+)\|([0-9]+)\]\]/g, () => {
    const ref = inlineRefs[idx]
    idx += 1
    if (!ref) return ''
    return `<span class="reference-link clickable" data-file-id="${ref.fileId}" data-page="${ref.page}">[${idx}]</span>`
  })
}

// 跳转到文档指定页码（由 PPTViewer 负责切文档 + 加载 + 跳页）
const jumpToDocumentPage = async (fileId, page) => {
  // 切换到 Documents 标签
  activeTab.value = 'documents'
  
  // 如果侧边栏折叠，展开它
  if (isPanelCollapsed.value) {
    isPanelCollapsed.value = false
  }
  
  // 等待 DOM 更新，确保 PPTViewer 已挂载
  await nextTick()
  
  const viewer = pptViewerRef.value
  const pageNumber = Number(page)
  
  if (viewer && typeof viewer.loadDocumentAndJump === 'function') {
    viewer.loadDocumentAndJump(fileId, pageNumber)
  } else if (viewer && typeof viewer.jumpToPage === 'function') {
    // 兼容旧逻辑：如果没有新的封装方法，则仅在当前文档上跳页
    viewer.jumpToPage(pageNumber)
  }
}

// 格式化消息，识别警告提示并应用斜体样式，移除 think 标签
const formatMessageWithWarning = (text) => {
  if (!text) return ''
  
  // 先移除 think 标签
  let content = text.replace(/<(?:think|redacted_reasoning)>[\s\S]*?<\/(?:think|redacted_reasoning)>/gi, '')
  content = content.replace(/<(?:think|redacted_reasoning)>[\s\S]*$/gi, '')
  
  // 使用 marked 解析 Markdown
  let html = formatEnhancedMarkdown(content)
  
  // 处理错误消息
  html = html.replace(/\[Error:\s*(.*?)\]/g, '<span class="error-inline">⚠ $1</span>')

  // 处理警告提示
  html = html.replace(/(⚠️[^：:]*[：:][^<\n]*)/g, '<span class="warning-text">$1</span>')
  
  // 解析引用标记（传入原始文本以提取 References 映射）
  html = parseReferences(html, text)
  
  return html
}

// 处理引用链接点击事件
const handleReferenceClick = (event) => {
  // 向上查找最近的 .reference-link 元素（处理点击的是内部元素的情况）
  let target = event.target
  while (target && target !== event.currentTarget) {
    if (target.classList && target.classList.contains('reference-link') && target.classList.contains('clickable')) {
      const fileId = target.dataset.fileId
      const page = target.dataset.page
      if (fileId && page) {
        jumpToDocumentPage(fileId, page)
        event.preventDefault()
        event.stopPropagation()
      }
      return
    }
    target = target.parentElement
  }
}

// 在 Markdown 文本中先渲染 LaTeX 为 KaTeX HTML
const renderMathInText = (text) => {
  if (!text) return ''
  
  let result = text

  // 先处理块级公式：$$ ... $$
  result = result.replace(/\$\$([\s\S]+?)\$\$/g, (match, tex) => {
    const html = katex.renderToString(tex.trim(), {
      displayMode: true,
      throwOnError: false
    })
    return html
  })

  // 再处理行内公式：$ ... $
  result = result.replace(/\$([^$\n]+?)\$/g, (match, tex) => {
    const html = katex.renderToString(tex.trim(), {
      displayMode: false,
      throwOnError: false
    })
    return html
  })

  return result
}

// 使用 marked 库进行 Markdown 格式化
const formatEnhancedMarkdown = (text) => {
  if (!text) return ''
  
  try {
    // 先把 LaTeX 替换为 KaTeX HTML，再交给 marked 解析 Markdown
    const source = renderMathInText(text)
    const html = marked.parse(source)
    return html
  } catch (error) {
    console.error('Markdown 解析错误:', error)
    // 降级处理：简单转义并换行
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>')
  }
}
</script>

<style scoped>
.chat-workspace {
  position: fixed;
  top: 0;
  left: var(--sidebar-width, 260px); /* 使用CSS变量，默认260px */
  right: 0;
  bottom: 0;
  width: calc(100vw - var(--sidebar-width, 260px)); /* 使用CSS变量，默认260px */
  height: 100vh;
  display: flex;
  overflow: hidden;
  z-index: 1;
  transition: left 0.3s ease, width 0.3s ease; /* 添加过渡动画 */
}

/* Chat Main Area - 全屏对话区域 */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  position: relative;
  background-color: var(--bg-card);
  transition: margin-right 0.3s ease;
  min-width: 0; /* 允许 flex 收缩 */
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-primary);
  opacity: 0.8;
}

.logo-placeholder {
  width: 64px;
  height: 64px;
  background-color: var(--bg-sidebar);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
  font-size: 32px;
}

.welcome-text {
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 500;
}

/* Message List */
.message-list {
  display: flex;
  flex-direction: column;
  gap: 16px; /* 减小消息之间的间距 */
}

.message-row {
  display: flex;
  gap: 12px; /* 减小消息内部元素间距 */
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 13px;
  flex-shrink: 0;
}

.message-row.user .avatar {
  background-color: #E0DDD6;
  color: var(--text-secondary);
}

.message-row.assistant .avatar {
  background-color: var(--color-accent);
  color: white;
}

.message-content {
  flex: 1;
  min-width: 0;
}

.sender-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.bubble {
  font-family: var(--font-sans);
  font-size: 15px;
  line-height: 1.4; /* 进一步减小行高 */
  color: var(--text-primary);
  white-space: pre-wrap;
}

.user-message-wrapper {
  position: relative;
}

.user-bubble {
  position: relative;
  padding-right: 32px;
}

.edit-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s, background-color 0.2s;
}

.user-bubble:hover .edit-btn {
  opacity: 1;
}

.edit-btn:hover {
  background-color: var(--bg-sidebar);
  color: var(--text-primary);
}

.edit-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.edit-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.edit-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  font-family: var(--font-sans);
  font-size: 15px;
  line-height: 1.5;
  color: var(--text-primary);
  background-color: var(--bg-app);
  resize: vertical;
  min-height: 60px;
}

.edit-input:focus {
  outline: none;
  border-color: var(--border-focus);
}

.edit-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.edit-save-btn,
.edit-cancel-btn {
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s;
}

.edit-save-btn {
  background-color: var(--color-accent);
  color: white;
}

.edit-save-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.edit-save-btn:disabled {
  background-color: #E5E5E5;
  cursor: not-allowed;
  opacity: 0.6;
}

.edit-cancel-btn {
  background-color: var(--bg-sidebar);
  color: var(--text-primary);
}

.edit-cancel-btn:hover {
  background-color: var(--bg-app);
}

/* 减小 Markdown 渲染后的段落间距 */
.message-text :deep(p) {
  margin: 0.15em 0; /* 进一步减小段落间距 */
  line-height: 1.4;
}

.message-text :deep(p:first-child) {
  margin-top: 0;
}

.message-text :deep(p:last-child) {
  margin-bottom: 0;
}

/* 处理空段落（Markdown 渲染空行时产生的） */
.message-text :deep(p:empty) {
  margin: 0;
  height: 0;
  display: none;
}

/* 减小列表项间距 */
.message-text :deep(ul),
.message-text :deep(ol) {
  margin: 0em 0;
  padding-left: 1.5em;
}

.message-text :deep(li) {
  margin: 0em 0;
  line-height: 1.4;
}

/* Input Area */
.input-area-wrapper {
  padding: 20px;
  border-top: 1px solid var(--border-subtle);
  background-color: var(--bg-card);
  border-radius: 0 0 12px 12px;
}

.input-box {
  background-color: var(--bg-app);
  border: 1.5px solid var(--border-subtle);
  border-radius: 16px;
  padding: 12px 16px;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.input-box:focus-within {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px rgba(218, 119, 86, 0.1), 0 1px 4px rgba(0, 0, 0, 0.04);
}

.chat-input {
  flex: 1;
  border: none;
  background: transparent;
  resize: none;
  font-family: var(--font-sans);
  font-size: 15px;
  line-height: 1.5;
  color: var(--text-primary);
  max-height: 200px;
  padding: 4px 0;
}

.chat-input:focus {
  outline: none;
}

.send-btn {
  background-color: var(--color-accent);
  color: white;
  border: none;
  border-radius: 10px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 18px;
}

.send-btn:hover:not(:disabled) {
  background-color: var(--color-accent-hover);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(218, 119, 86, 0.3);
}

.send-btn:disabled {
  background-color: var(--border-subtle);
  cursor: not-allowed;
}

.stop-btn {
  background-color: var(--bg-app);
  border: 2px solid var(--text-tertiary);
  border-radius: 10px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.stop-btn:hover {
  border-color: var(--color-accent);
}

.stop-icon {
  display: block;
  width: 12px;
  height: 12px;
  background-color: var(--text-secondary);
  border-radius: 2px;
  transition: background-color 0.2s;
}

.stop-btn:hover .stop-icon {
  background-color: var(--color-accent);
}

.input-footer {
  text-align: center;
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 8px;
}

/* 右侧可折叠侧边栏（集成在对话区域内） */
.sidebar-panel {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  min-width: 300px;
  background-color: var(--bg-card);
  border-left: 1px solid var(--border-subtle);
  box-shadow: -2px 0 8px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
  transition: transform 0.3s ease, width 0.1s ease;
  z-index: 100;
  overflow: hidden;
}

.sidebar-panel.collapsed {
  transform: translateX(100%);
  width: 0 !important;
}

/* 拖动调整大小的分隔条 */
.sidebar-resizer {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  cursor: col-resize;
  z-index: 102;
  background-color: transparent;
  transition: background-color 0.2s;
}

.sidebar-resizer:hover {
  background-color: var(--color-accent);
}

.sidebar-resizer:active {
  background-color: var(--color-accent);
}

.sidebar-toggle {
  position: absolute;
  top: 50%;
  left: 0;
  transform: translate(-100%, -50%);
  width: 24px;
  height: 48px;
  background-color: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-right: none;
  border-radius: 8px 0 0 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 101;
  box-shadow: -2px 0 8px rgba(0,0,0,0.1);
  transition: all 0.2s;
}

.sidebar-toggle:hover {
  background-color: var(--bg-sidebar);
}

.sidebar-content {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.sidebar-tabs :deep(.el-tabs__header) {
  margin: 0;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
}

.sidebar-tabs :deep(.el-tabs__content) {
  flex: 1;
  padding: 0;
  overflow: hidden;
}

.sidebar-tabs :deep(.el-tab-pane) {
  height: 100%;
}

.tab-content-wrapper {
  height: 100%;
  width: 100%;
  overflow: hidden;
  background-color: #fff;
}

.docs-panel {
  height: 100%;
  width: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Markdown 和 LaTeX 渲染样式 */
.message-text {
  line-height: 1.4; /* 统一行高 */
  word-wrap: break-word;
}

.message-text :deep(code) {
  background-color: rgba(0, 0, 0, 0.1);
  padding: 2px 4px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
}

.message-text :deep(pre) {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
  margin: 8px 0;
}

.message-text :deep(pre code) {
  background-color: transparent;
  padding: 0;
}

.message-text :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}

.message-text :deep(table th),
.message-text :deep(table td) {
  border: 1px solid var(--border-subtle);
  padding: 8px 12px;
  text-align: left;
}

.message-text :deep(table th) {
  background-color: var(--bg-sidebar);
  font-weight: 600;
}

.message-text :deep(blockquote) {
  border-left: 3px solid var(--color-accent);
  padding-left: 12px;
  margin: 8px 0;
  color: var(--text-secondary);
}

.warning-text {
  font-style: italic;
  color: var(--text-tertiary);
}

.message-text :deep(.error-inline) {
  display: inline-block;
  background-color: #FEF0F0;
  color: #F56C6C;
  border: 1px solid #FDE2E2;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 13px;
  margin: 4px 0;
}

.message-text :deep(.reference-link) {
  color: #409eff;
  text-decoration: underline;
  transition: all 0.2s;
}

.message-text :deep(.reference-link.clickable) {
  cursor: pointer;
  font-weight: 500;
  background-color: rgba(64, 158, 255, 0.1);
  padding: 2px 4px;
  border-radius: 3px;
}

.message-text :deep(.reference-link.clickable:hover) {
  color: #66b1ff;
  background-color: rgba(64, 158, 255, 0.2);
}

.message-text :deep(.reference-number) {
  color: #909399;
  font-weight: normal;
}

.tool-calls-section {
  margin: 12px 0;
}

.think-section {
  margin-bottom: 12px;
}

.think-content {
  padding: 12px;
  background-color: var(--bg-sidebar);
  border-radius: 4px;
  font-size: 0.9em;
  line-height: 1.6;
}

/* KaTeX 样式 */
.message-text :deep(.katex) {
  font-size: 1.1em;
}

.message-text :deep(.katex-display) {
  margin: 16px 0;
  overflow-x: auto;
  overflow-y: hidden;
}
</style>

