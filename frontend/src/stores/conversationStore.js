import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import conversationService from '../services/conversationService'

export const useConversationStore = defineStore('conversation', () => {
  // 状态
  const conversations = ref([])
  const currentConversationId = ref(null)
  const loading = ref(false)
  const error = ref(null)

  // 计算属性
  const currentConversation = computed(() => {
    if (!currentConversationId.value) return null
    return conversations.value.find(c => c.conversation_id === currentConversationId.value)
  })

  const conversationCount = computed(() => conversations.value.length)

  // Actions
  /**
   * 加载对话列表
   */
  async function loadConversations(statusFilter = null) {
    loading.value = true
    error.value = null
    try {
      const response = await conversationService.getConversations(statusFilter)
      conversations.value = response.conversations || []
      return response
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 创建新对话
   */
  async function createConversation(title = null) {
    loading.value = true
    error.value = null
    try {
      const conversation = await conversationService.createConversation(title)
      conversations.value.unshift(conversation)
      return conversation
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取对话详情（如果不在列表中则单独获取）
   */
  async function loadConversation(conversationId) {
    loading.value = true
    error.value = null
    try {
      // 先检查是否已在列表中
      let conversation = conversations.value.find(c => c.conversation_id === conversationId)
      
      if (!conversation) {
        // 不在列表中，单独获取
        conversation = await conversationService.getConversation(conversationId)
        conversations.value.unshift(conversation)
      }
      
      return conversation
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 选择对话
   */
  function selectConversation(conversationId) {
    currentConversationId.value = conversationId
  }

  /**
   * 删除对话
   */
  async function deleteConversation(conversationId) {
    loading.value = true
    error.value = null
    try {
      await conversationService.deleteConversation(conversationId)
      
      // 从列表中移除
      const index = conversations.value.findIndex(c => c.conversation_id === conversationId)
      if (index !== -1) {
        conversations.value.splice(index, 1)
      }
      
      // 如果删除的是当前对话，清空选择
      if (currentConversationId.value === conversationId) {
        currentConversationId.value = null
      }
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 更新对话（刷新本地数据）
   */
  async function refreshConversation(conversationId) {
    try {
      const conversation = await conversationService.getConversation(conversationId)
      const index = conversations.value.findIndex(c => c.conversation_id === conversationId)
      if (index !== -1) {
        conversations.value[index] = conversation
      } else {
        conversations.value.unshift(conversation)
      }
      return conversation
    } catch (err) {
      error.value = err
      throw err
    }
  }

  /**
   * 更新对话信息（重命名、置顶等）
   */
  async function updateConversation(conversationId, data) {
    loading.value = true
    error.value = null
    try {
      const updated = await conversationService.updateConversation(conversationId, data)
      
      // 更新本地列表
      const index = conversations.value.findIndex(c => c.conversation_id === conversationId)
      if (index !== -1) {
        conversations.value[index] = updated
      }
      
      // 如果更新了置顶状态，重新排序
      if (data.pinned !== undefined) {
        sortConversations()
      }
      
      return updated
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 对对话列表排序（置顶的在前，然后按更新时间倒序）
   */
  function sortConversations() {
    const pinned = conversations.value.filter(c => c.pinned)
    const unpinned = conversations.value.filter(c => !c.pinned)
    pinned.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
    unpinned.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
    conversations.value = [...pinned, ...unpinned]
  }

  /**
   * 清空状态
   */
  function reset() {
    conversations.value = []
    currentConversationId.value = null
    loading.value = false
    error.value = null
  }

  return {
    // 状态
    conversations,
    currentConversationId,
    loading,
    error,
    // 计算属性
    currentConversation,
    conversationCount,
    // Actions
    loadConversations,
    createConversation,
    loadConversation,
    selectConversation,
    deleteConversation,
    updateConversation,
    refreshConversation,
    sortConversations,
    reset
  }
})

