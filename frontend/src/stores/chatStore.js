import { defineStore } from 'pinia'
import { ref } from 'vue'
import chatService from '../services/chatService'

export const useChatStore = defineStore('chat', () => {
  // 状态：每个对话的消息列表 { conversationId: [messages] }
  const messages = ref({})
  
  // Actions
  /**
   * 获取对话的消息列表
   */
  function getMessages(conversationId) {
    if (!conversationId) return []
    return messages.value[conversationId] || []
  }
  
  /**
   * 添加消息到对话
   */
  function addMessage(conversationId, message) {
    if (!conversationId) return
    
    if (!messages.value[conversationId]) {
      messages.value[conversationId] = []
    }
    
    messages.value[conversationId].push(message)
  }
  
  /**
   * 加载对话历史消息
   */
  async function loadMessages(conversationId) {
    if (!conversationId) return
    
    try {
      const history = await chatService.getHistory(conversationId)
      messages.value[conversationId] = history.messages || []
    } catch (error) {
      console.error('加载消息历史失败:', error)
      // 如果加载失败，初始化为空数组
      if (!messages.value[conversationId]) {
        messages.value[conversationId] = []
      }
    }
  }
  
  /**
   * 流式查询
   */
  async function queryStream(conversationId, query, mode, onChunk) {
    if (!conversationId) throw new Error('请先选择对话')
    
    await chatService.queryStream(conversationId, query, mode, onChunk)
  }
  
  /**
   * 保存消息到后端
   */
  async function saveMessage(conversationId, query, answer) {
    if (!conversationId) return
    
    try {
      await chatService.saveMessage(conversationId, query, answer)
    } catch (error) {
      console.error('保存消息失败:', error)
      // 保存失败不影响用户体验，只记录错误
    }
  }
  
  /**
   * 清空对话消息
   */
  function clearMessages(conversationId = null) {
    if (conversationId) {
      delete messages.value[conversationId]
    } else {
      messages.value = {}
    }
  }
  
  return {
    messages,
    getMessages,
    addMessage,
    loadMessages,
    queryStream,
    saveMessage,
    clearMessages
  }
})

