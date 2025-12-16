<template>
  <div class="chat-workspace">
    <!-- 对话区域（全屏） -->
    <div class="chat-main" :style="{ marginRight: isPanelCollapsed ? '0' : `${sidebarWidth}px` }">
      <!-- 消息列表区域 -->
      <div class="messages-container" ref="messagesContainer">
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
              <div class="bubble">
                {{ msg.content }}
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
            class="send-btn" 
            :disabled="!inputMessage.trim() || isLoading"
            @click="handleSend"
          >
            <el-icon><Position /></el-icon>
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
          <!-- 思维导图 Tab -->
          <el-tab-pane label="Mind Map" name="mindmap">
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
import { Position, ArrowRight, ArrowLeft, Share } from '@element-plus/icons-vue'
import { marked } from 'marked'
import katex from 'katex'
import { useConversationStore } from './store/conversationStore'
import { useDocumentStore } from '../documents/store/documentStore'
import { useChatStore } from './store/chatStore'
import GraphViewer from '../graph/components/GraphViewer.vue'
import MindMapViewer from '../mindmap/components/MindMapViewer.vue'
import PPTViewer from '../documents/components/PPTViewer/PPTViewer.vue'
import ToolCallInline from './components/ToolCallInline.vue'
import { api, BASE_URL } from '../../services/api'

// 配置 marked 选项
marked.setOptions({
  breaks: true, // 支持换行
  gfm: true,    // 支持 GitHub 风格 Markdown
})

const route = useRoute()
const conversationId = route.params.id
const convStore = useConversationStore()
const docStore = useDocumentStore()
const chatStore = useChatStore()

const inputMessage = ref('')
const isLoading = ref(false)
const messagesContainer = ref(null)
const textareaRef = ref(null)

// 面板状态
const isPanelCollapsed = ref(false)
const activeTab = ref('mindmap')
const showGraphModal = ref(false)

// 侧边栏宽度（可拖动调整）
const sidebarWidth = ref(400)
const isResizing = ref(false)
const minSidebarWidth = 300
const maxSidebarWidth = 800

// Think 内容折叠状态
const thinkCollapseStates = ref([])

// 消息数据
const messages = ref([])

// 当前选中的文档ID（用于 PPT 查看器）
const selectedDocumentId = ref(null)

// 获取当前对话的文档
const currentDocuments = computed(() => {
  if (!conversationId) return []
  return docStore.getDocumentsByConversation(conversationId) || []
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
  try {
    const res = await api.get(`/api/conversations/${conversationId}/messages`)
    if (res.messages) {
      // 过滤掉 tool 角色的消息，这些消息不应该显示给用户
      // tool 消息包含大量的工具执行结果数据，会导致性能问题
      messages.value = res.messages
        .filter(m => m.role !== 'tool') // 过滤 tool 消息
        .map(m => ({
        role: m.role === 'human' ? 'user' : m.role, // 兼容后端可能返回 human
          content: m.content || '',
          streamItems: m.streamItems || null, // 保留 streamItems（工具调用信息在这里）
          toolCalls: m.toolCalls || null // 保留 toolCalls（向后兼容）
      }))
      scrollToBottom()
    }
  } catch (e) {
    console.error('Failed to load messages:', e)
  }
}

const handleSend = async () => {
  if (!inputMessage.value.trim() || isLoading.value) return

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
    const response = await fetch(`${BASE_URL}/api/conversations/${conversationId}/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: content,
        mode: 'agent' // 使用 agent 模式以支持工具调用
      })
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
          conversationId,
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
    // streamItems 已经是响应式数组的引用，无需重新赋值
    
    // 即使出错也尝试保存消息
    try {
      await chatStore.saveMessage(
        conversationId,
        content,
        messages.value[aiMessageIndex].content,
        null,
        streamItems.length > 0 ? [...streamItems] : null
      )
    } catch (saveError) {
      console.error('❌ 保存错误消息失败:', saveError)
    }
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

onMounted(async () => {
  console.log('🚀 ChatView mounted, conversationId:', conversationId)
  
  // 确保对话被加载
  if (conversationId && (!convStore.currentConversationId || convStore.currentConversationId !== conversationId)) {
    console.log('🔄 Loading conversation details...')
    await convStore.loadConversation(conversationId)
    convStore.selectConversation(conversationId)
  }
  
  // 加载文档
  console.log('📂 Loading documents for:', conversationId)
  try {
    await docStore.loadDocuments(conversationId)
    const docs = docStore.getDocumentsByConversation(conversationId)
    console.log('✅ Documents loaded:', docs)
    
    // 自动选择第一个支持的文档（PPTX 或 PDF）
    if (docs && docs.length > 0) {
      const pptxDoc = docs.find(doc => doc.file_extension === 'pptx')
      const pdfDoc = docs.find(doc => doc.file_extension === 'pdf')
      selectedDocumentId.value = (pptxDoc || pdfDoc)?.file_id || null
      console.log('📄 自动选择文档:', selectedDocumentId.value)
    }
  } catch (e) {
    console.error('❌ Failed to load documents:', e)
  }

  // 加载历史
  console.log('💬 Loading messages...')
  await loadMessages()
})

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

// 格式化消息，识别警告提示并应用斜体样式，移除 think 标签
const formatMessageWithWarning = (text) => {
  if (!text) return ''
  
  // 先移除 think 标签
  let content = text.replace(/<(?:think|redacted_reasoning)>[\s\S]*?<\/(?:think|redacted_reasoning)>/gi, '')
  content = content.replace(/<(?:think|redacted_reasoning)>[\s\S]*$/gi, '')
  
  // 使用 marked 解析 Markdown
  let html = formatEnhancedMarkdown(content)
  
  // 处理警告提示
  html = html.replace(/(⚠️[^：:]*[：:][^<\n]*)/g, '<span class="warning-text">$1</span>')
  
  return html
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
  left: 260px; /* 左侧边栏宽度 */
  right: 0;
  bottom: 0;
  width: calc(100vw - 260px); /* 全屏宽度减去侧边栏 */
  height: 100vh;
  display: flex;
  overflow: hidden;
  z-index: 1;
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
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
}

.message-row.user .avatar {
  background-color: #E5E5E5;
  color: #333;
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
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 12px 16px;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  transition: border-color 0.2s;
}

.input-box:focus-within {
  border-color: var(--border-focus);
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
  border-radius: 8px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn:disabled {
  background-color: #E5E5E5;
  cursor: not-allowed;
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

