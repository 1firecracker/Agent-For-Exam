import { defineStore } from 'pinia'
import { ref } from 'vue'
import chatService from '../services/chatService'

export const useChatStore = defineStore('chat', () => {
  const messages = ref({})
  
  function getMessages(conversationId) {
    if (!conversationId) return []
    return messages.value[conversationId] || []
  }
  
  function addMessage(conversationId, message) {
    if (!conversationId) return
    
    if (!messages.value[conversationId]) {
      messages.value[conversationId] = []
    }
    
    messages.value[conversationId].push(message)
  }
  
  async function loadMessages(conversationId) {
    if (!conversationId) return
    
    try {
      const history = await chatService.getHistory(conversationId)
      const loadedMessages = history.messages || []
      
      const processedMessages = loadedMessages.map(msg => {
        const processedMsg = { ...msg }
        
        if (processedMsg.streamItems && Array.isArray(processedMsg.streamItems)) {
          processedMsg.streamItems = processedMsg.streamItems.map(item => {
            if (item.type === 'tool_call') {
              const needsFix = !item.status || item.status === 'pending' || item.status === '' || item.status === null || item.status === undefined
              
              if (needsFix) {
                if (item.result) {
                  item.status = 'success'
                } else if (item.errorMessage) {
                  item.status = 'error'
                } else {
                  item.status = 'success'
                }
              }
            }
            return item
          })
        }
        
        if (processedMsg.toolCalls && Array.isArray(processedMsg.toolCalls)) {
          processedMsg.toolCalls = processedMsg.toolCalls.map(tc => {
            const needsFix = !tc.status || tc.status === 'pending' || tc.status === '' || tc.status === null || tc.status === undefined
            
            if (needsFix) {
              if (tc.result) {
                tc.status = 'success'
              } else if (tc.errorMessage) {
                tc.status = 'error'
              } else {
                tc.status = 'success'
              }
            }
            return tc
          })
        }
        
        return processedMsg
      })
      
      messages.value[conversationId] = processedMessages
    } catch (error) {
      console.error('加载消息历史失败:', error)
      if (!messages.value[conversationId]) {
        messages.value[conversationId] = []
      }
    }
  }
  
  async function queryStream(conversationId, query, mode, agentIntent, onChunk) {
    if (!conversationId) throw new Error('请先选择对话')
    
    await chatService.queryStream(conversationId, query, mode, agentIntent, onChunk)
  }
  
  async function saveMessage(conversationId, query, answer, toolCalls = null, streamItems = null) {
    if (!conversationId) return
    
    try {
      await chatService.saveMessage(conversationId, query, answer, toolCalls, streamItems)
    } catch (error) {
      console.error('保存消息失败:', error)
    }
  }
  
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


