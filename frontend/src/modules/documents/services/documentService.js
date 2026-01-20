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

  // ========== 按 subjectId 操作文档的方法 ==========
  
  async uploadDocumentsForSubject(subjectId, files, onProgress) {
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
      `/api/subjects/${subjectId}/documents/upload`,
      formData,
      config
    )
    return response
  }

  async getDocumentsForSubject(subjectId) {
    const response = await api.get(`/api/subjects/${subjectId}/documents`)
    return response
  }

  async getDocumentForSubject(subjectId, fileId) {
    const response = await api.get(`/api/subjects/${subjectId}/documents/${fileId}`)
    return response
  }

  async getDocumentStatusForSubject(subjectId, fileId) {
    const response = await api.get(`/api/subjects/${subjectId}/documents/${fileId}/status`)
    return response
  }

  async deleteDocumentForSubject(subjectId, fileId) {
    await api.delete(`/api/subjects/${subjectId}/documents/${fileId}`)
  }

  async getDocumentSlidesForSubject(subjectId, fileId) {
    const response = await api.get(`/api/subjects/${subjectId}/documents/${fileId}/slides`)
    return response
  }

  async getSlideForSubject(subjectId, fileId, slideId) {
    const response = await api.get(
      `/api/subjects/${subjectId}/documents/${fileId}/slides/${slideId}`
    )
    return response
  }

  getSlideImageUrlForSubject(subjectId, fileId, slideId, useCache = true) {
    const timestamp = new Date().getTime()
    return `/api/subjects/${subjectId}/documents/${fileId}/slides/${slideId}/image?use_cache=${useCache}&_t=${timestamp}`
  }

  getSlideThumbnailUrlForSubject(subjectId, fileId, slideId, useCache = true) {
    const timestamp = new Date().getTime()
    return `/api/subjects/${subjectId}/documents/${fileId}/slides/${slideId}/thumbnail?use_cache=${useCache}&_t=${timestamp}`
  }
}

export default new DocumentService()


