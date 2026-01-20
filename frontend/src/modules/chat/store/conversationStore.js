import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import conversationService from '../services/conversationService'

export const useConversationStore = defineStore('conversation', () => {
  const conversations = ref([])
  const currentConversationId = ref(null)
  const loading = ref(false)
  const error = ref(null)

  const currentConversation = computed(() => {
    if (!currentConversationId.value) return null
    return conversations.value.find(c => c.conversation_id === currentConversationId.value)
  })

  const conversationCount = computed(() => conversations.value.length)

  const getConversationsBySubject = computed(() => {
    return (subjectId) => {
      if (!subjectId) return []
      return conversations.value.filter(c => c.subject_id === subjectId)
    }
  })

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

  async function loadConversation(conversationId) {
    loading.value = true
    error.value = null
    try {
      let conversation = conversations.value.find(c => c.conversation_id === conversationId)
      
      if (!conversation) {
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

  function selectConversation(conversationId) {
    currentConversationId.value = conversationId
  }

  async function deleteConversation(conversationId) {
    loading.value = true
    error.value = null
    try {
      await conversationService.deleteConversation(conversationId)
      
      const index = conversations.value.findIndex(c => c.conversation_id === conversationId)
      if (index !== -1) {
        conversations.value.splice(index, 1)
      }
      
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

  async function updateConversation(conversationId, data) {
    loading.value = true
    error.value = null
    try {
      const updated = await conversationService.updateConversation(conversationId, data)
      
      const index = conversations.value.findIndex(c => c.conversation_id === conversationId)
      if (index !== -1) {
        conversations.value[index] = updated
      }
      
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

  function sortConversations() {
    const pinned = conversations.value.filter(c => c.pinned)
    const unpinned = conversations.value.filter(c => !c.pinned)
    pinned.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
    unpinned.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
    conversations.value = [...pinned, ...unpinned]
  }

  function reset() {
    conversations.value = []
    currentConversationId.value = null
    loading.value = false
    error.value = null
  }

  return {
    conversations,
    currentConversationId,
    loading,
    error,
    currentConversation,
    conversationCount,
    getConversationsBySubject,
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


