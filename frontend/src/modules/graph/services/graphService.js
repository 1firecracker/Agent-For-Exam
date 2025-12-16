import { api } from '../../../services/api'

class GraphService {
  async getGraph(conversationId) {
    const response = await api.get(`/api/conversations/${conversationId}/graph`)
    return response
  }

  async getEntity(conversationId, entityId) {
    const response = await api.get(
      `/api/conversations/${conversationId}/graph/entities/${encodeURIComponent(entityId)}`
    )
    return response
  }

  async query(conversationId, query, mode = 'naive') {
    const response = await api.post(`/api/conversations/${conversationId}/query`, {
      query,
      mode
    })
    return response
  }

  async getRelation(conversationId, source, target) {
    const response = await api.get(`/api/conversations/${conversationId}/graph/relations`, {
      params: { source, target }
    })
    return response
  }

  async getGraphStatus(conversationId) {
    const response = await api.get(`/api/conversations/${conversationId}/graph/status`)
    return response
  }
}

export default new GraphService()


