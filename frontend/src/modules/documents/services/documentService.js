import { api } from '../../../services/api'

class DocumentService {
  async uploadDocuments(conversationId, files, onProgress) {
    const formData = new FormData()
    const fileArray = Array.isArray(files) ? files : [files]
    fileArray.forEach(file => {
      formData.append('files', file)
    })
    
    const config = {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    }
    
    if (onProgress && typeof onProgress === 'function') {
      config.onUploadProgress = (progressEvent) => {
        if (progressEvent.total) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          )
          onProgress(percentCompleted)
        }
      }
    }
    
    const response = await api.post(
      `/api/conversations/${conversationId}/documents/upload`,
      formData,
      config
    )
    return response
  }

  async getDocuments(conversationId) {
    const response = await api.get(`/api/conversations/${conversationId}/documents`)
    return response
  }

  async getDocument(conversationId, fileId) {
    const response = await api.get(`/api/conversations/${conversationId}/documents/${fileId}`)
    return response
  }

  async getDocumentStatus(conversationId, fileId) {
    const response = await api.get(`/api/conversations/${conversationId}/documents/${fileId}/status`)
    return response
  }

  async deleteDocument(conversationId, fileId) {
    await api.delete(`/api/conversations/${conversationId}/documents/${fileId}`)
  }

  async getDocumentSlides(conversationId, fileId) {
    const response = await api.get(`/api/conversations/${conversationId}/documents/${fileId}/slides`)
    return response
  }

  async getSlide(conversationId, fileId, slideId) {
    const response = await api.get(
      `/api/conversations/${conversationId}/documents/${fileId}/slides/${slideId}`
    )
    return response
  }

  getSlideImageUrl(conversationId, fileId, slideId, useCache = true) {
    const timestamp = new Date().getTime()
    return `/api/conversations/${conversationId}/documents/${fileId}/slides/${slideId}/image?use_cache=${useCache}&_t=${timestamp}`
  }

  getSlideThumbnailUrl(conversationId, fileId, slideId, useCache = true) {
    const timestamp = new Date().getTime()
    return `/api/conversations/${conversationId}/documents/${fileId}/slides/${slideId}/thumbnail?use_cache=${useCache}&_t=${timestamp}`
  }
}

export default new DocumentService()


