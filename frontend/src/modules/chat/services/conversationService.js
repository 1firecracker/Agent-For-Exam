import { api } from '../../../services/api'

class ConversationService {
  async createConversation(title = null) {
    const response = await api.post('/api/conversations', {
      title: title || undefined
    })
    return response
  }

  async getConversations(statusFilter = null) {
    const params = statusFilter ? { status_filter: statusFilter } : {}
    const response = await api.get('/api/conversations', { params })
    return response
  }

  async getConversation(conversationId) {
    const response = await api.get(`/api/conversations/${conversationId}`)
    return response
  }

  async deleteConversation(conversationId) {
    await api.delete(`/api/conversations/${conversationId}`)
  }

  async updateConversation(conversationId, data) {
    const response = await api.patch(`/api/conversations/${conversationId}`, data)
    return response
  }
}

export default new ConversationService()


