import { api } from './api'

/**
 * 对话管理服务
 */
class ConversationService {
  /**
   * 创建新对话
   * @param {string|null} title - 对话标题（可选，不提供则自动生成编号）
   * @returns {Promise<Object>} 对话对象
   */
  async createConversation(title = null) {
    const response = await api.post('/api/conversations', {
      title: title || undefined
    })
    return response
  }

  /**
   * 获取对话列表
   * @param {string|null} statusFilter - 状态过滤（可选：active/archived）
   * @returns {Promise<Object>} 包含 conversations 和 total 的对象
   */
  async getConversations(statusFilter = null) {
    const params = statusFilter ? { status_filter: statusFilter } : {}
    const response = await api.get('/api/conversations', { params })
    return response
  }

  /**
   * 获取对话详情
   * @param {string} conversationId - 对话ID
   * @returns {Promise<Object>} 对话对象
   */
  async getConversation(conversationId) {
    const response = await api.get(`/api/conversations/${conversationId}`)
    return response
  }

  /**
   * 删除对话
   * @param {string} conversationId - 对话ID
   * @returns {Promise<void>}
   */
  async deleteConversation(conversationId) {
    await api.delete(`/api/conversations/${conversationId}`)
  }
}

export default new ConversationService()

