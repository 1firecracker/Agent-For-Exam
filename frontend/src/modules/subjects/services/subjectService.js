import { api } from '../../../services/api'

class SubjectService {
  async createSubject(name = null, description = null) {
    const response = await api.post('/api/subjects', {
      name: name || undefined,
      description: description || undefined
    })
    return response
  }

  async getSubjects() {
    const response = await api.get('/api/subjects')
    return response
  }

  async getSubject(subjectId) {
    const response = await api.get(`/api/subjects/${subjectId}`)
    return response
  }

  async getConversationsBySubject(subjectId, statusFilter = null) {
    const params = statusFilter ? { status_filter: statusFilter } : {}
    const response = await api.get(`/api/subjects/${subjectId}/conversations`, { params })
    return response
  }

  async createConversationForSubject(subjectId, title = null) {
    const response = await api.post(`/api/subjects/${subjectId}/conversations`, {
      title: title || undefined
    })
    return response
  }

  async updateSubject(subjectId, name = null, description = null) {
    const response = await api.patch(`/api/subjects/${subjectId}`, {
      name: name || undefined,
      description: description || undefined
    })
    return response
  }

  async deleteSubject(subjectId) {
    await api.delete(`/api/subjects/${subjectId}`)
  }
}

export default new SubjectService()


