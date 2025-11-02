import { api } from './api'

/**
 * 文档管理服务
 */
class DocumentService {
  /**
   * 上传文档
   * @param {string} conversationId - 对话ID（使用 'new' 自动创建对话）
   * @param {File|File[]} files - 文件或文件数组
   * @param {Function} onProgress - 进度回调函数 (percent) => void
   * @returns {Promise<Object>} 上传结果
   */
  async uploadDocuments(conversationId, files, onProgress) {
    const formData = new FormData()
    
    // 支持单个文件或多个文件
    const fileArray = Array.isArray(files) ? files : [files]
    fileArray.forEach(file => {
      formData.append('files', file)
    })
    
    const config = {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    }
    
    // 如果提供了进度回调，添加上传进度监听
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

  /**
   * 获取对话的文档列表
   * @param {string} conversationId - 对话ID
   * @returns {Promise<Object>} 包含 documents 和 total 的对象
   */
  async getDocuments(conversationId) {
    const response = await api.get(`/api/conversations/${conversationId}/documents`)
    return response
  }

  /**
   * 获取文档详情
   * @param {string} conversationId - 对话ID
   * @param {string} fileId - 文件ID
   * @returns {Promise<Object>} 文档对象
   */
  async getDocument(conversationId, fileId) {
    const response = await api.get(`/api/conversations/${conversationId}/documents/${fileId}`)
    return response
  }

  /**
   * 查询文档处理状态
   * @param {string} conversationId - 对话ID
   * @param {string} fileId - 文件ID
   * @returns {Promise<Object>} 状态信息
   */
  async getDocumentStatus(conversationId, fileId) {
    const response = await api.get(`/api/conversations/${conversationId}/documents/${fileId}/status`)
    return response
  }

  /**
   * 删除文档
   * @param {string} conversationId - 对话ID
   * @param {string} fileId - 文件ID
   * @returns {Promise<void>}
   */
  async deleteDocument(conversationId, fileId) {
    await api.delete(`/api/conversations/${conversationId}/documents/${fileId}`)
  }

  /**
   * 获取文档的所有幻灯片（仅支持PPTX）
   * @param {string} conversationId - 对话ID
   * @param {string} fileId - 文件ID
   * @returns {Promise<Object>} 幻灯片列表
   */
  async getDocumentSlides(conversationId, fileId) {
    const response = await api.get(`/api/conversations/${conversationId}/documents/${fileId}/slides`)
    return response
  }

  /**
   * 获取单个幻灯片（仅支持PPTX）
   * @param {string} conversationId - 对话ID
   * @param {string} fileId - 文件ID
   * @param {number} slideId - 幻灯片编号（从1开始）
   * @returns {Promise<Object>} 幻灯片对象
   */
  async getSlide(conversationId, fileId, slideId) {
    const response = await api.get(
      `/api/conversations/${conversationId}/documents/${fileId}/slides/${slideId}`
    )
    return response
  }

  /**
   * 获取幻灯片/页面的渲染图片URL
   * @param {string} conversationId - 对话ID
   * @param {string} fileId - 文件ID
   * @param {number} slideId - 幻灯片/页面编号（从1开始）
   * @param {boolean} [useCache=true] - 是否使用缓存
   * @returns {string} 图片URL
   */
  getSlideImageUrl(conversationId, fileId, slideId, useCache = true) {
    const baseURL = api.defaults.baseURL || 'http://localhost:8000'
    return `${baseURL}/api/conversations/${conversationId}/documents/${fileId}/slides/${slideId}/image?use_cache=${useCache}`
  }

  /**
   * 获取幻灯片/页面的缩略图URL
   * @param {string} conversationId - 对话ID
   * @param {string} fileId - 文件ID
   * @param {number} slideId - 幻灯片/页面编号（从1开始）
   * @param {boolean} [useCache=true] - 是否使用缓存
   * @returns {string} 缩略图URL
   */
  getSlideThumbnailUrl(conversationId, fileId, slideId, useCache = true) {
    const baseURL = api.defaults.baseURL || 'http://localhost:8000'
    return `${baseURL}/api/conversations/${conversationId}/documents/${fileId}/slides/${slideId}/thumbnail?use_cache=${useCache}`
  }
}

export default new DocumentService()

