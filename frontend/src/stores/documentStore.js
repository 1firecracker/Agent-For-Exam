import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import documentService from '../services/documentService'

export const useDocumentStore = defineStore('document', () => {
  // 状态
  const documents = ref({}) // { conversationId: [documents] }
  const uploading = ref(false)
  const uploadProgress = ref(0) // 上传进度 0-100
  const uploadingFileName = ref('') // 当前上传的文件名
  const loading = ref(false)
  const error = ref(null)
  
  // 知识提取进度状态
  // { conversationId: { fileId: { fileName, status, progress, error } } }
  const extractionProgress = ref({})
  const extractionPollingTimers = ref({}) // { conversationId: timerId }

  // 计算属性
  /**
   * 获取指定对话的文档列表
   */
  const getDocumentsByConversation = computed(() => {
    return (conversationId) => {
      return documents.value[conversationId] || []
    }
  })

  /**
   * 获取指定对话的文档数量
   */
  const getDocumentCount = computed(() => {
    return (conversationId) => {
      return documents.value[conversationId]?.length || 0
    }
  })

  // Actions
  /**
   * 上传文档
   * @param {string} conversationId - 对话ID
   * @param {File|File[]} files - 文件或文件数组
   * @param {Function} onProgress - 可选，进度回调函数
   */
  async function uploadDocuments(conversationId, files, onProgress) {
    uploading.value = true
    uploadProgress.value = 0
    error.value = null
    
    // 获取文件名（用于显示）
    const fileArray = Array.isArray(files) ? files : [files]
    uploadingFileName.value = fileArray.length === 1 ? fileArray[0].name : `${fileArray.length} 个文件`
    
    // 内部进度回调
    const internalProgressCallback = (percent) => {
      uploadProgress.value = percent
      if (onProgress && typeof onProgress === 'function') {
        onProgress(percent)
      }
    }
    
    try {
      const response = await documentService.uploadDocuments(
        conversationId, 
        files, 
        internalProgressCallback
      )
      
      // 上传完成，进度设为100%
      uploadProgress.value = 100
      
      // 如果自动创建了对话，返回 conversation_id
      const resultConversationId = response.conversation_id
      
      // 上传后需要重新加载文档列表
      if (resultConversationId) {
        await loadDocuments(resultConversationId)
      }
      
      // 开始监控知识提取进度（针对新上传的文件）
      if (response.uploaded_files && response.uploaded_files.length > 0) {
        startExtractionProgress(resultConversationId, response.uploaded_files)
      }
      
      return response
    } catch (err) {
      error.value = err
      uploadProgress.value = 0
      throw err
    } finally {
      uploading.value = false
      uploadingFileName.value = ''
      // 延迟重置进度，让用户看到100%
      setTimeout(() => {
        uploadProgress.value = 0
      }, 500)
    }
  }

  /**
   * 加载对话的文档列表
   */
  async function loadDocuments(conversationId) {
    loading.value = true
    error.value = null
    try {
      const response = await documentService.getDocuments(conversationId)
      documents.value[conversationId] = response.documents || []
      
      // 检查是否有正在处理的文档，如果有则启动进度监控
      const processingDocs = response.documents?.filter(
        doc => doc.status === 'pending' || doc.status === 'processing'
      ) || []
      
      if (processingDocs.length > 0) {
        const filesToMonitor = processingDocs.map(doc => ({
          file_id: doc.file_id,
          filename: doc.filename
        }))
        startExtractionProgress(conversationId, filesToMonitor)
      }
      
      return response
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取文档详情
   */
  async function getDocument(conversationId, fileId) {
    try {
      const document = await documentService.getDocument(conversationId, fileId)
      
      // 更新本地缓存
      const docs = documents.value[conversationId] || []
      const index = docs.findIndex(d => d.file_id === fileId)
      if (index !== -1) {
        docs[index] = document
      } else {
        docs.push(document)
      }
      documents.value[conversationId] = docs
      
      return document
    } catch (err) {
      error.value = err
      throw err
    }
  }

  /**
   * 查询文档处理状态
   */
  async function getDocumentStatus(conversationId, fileId) {
    try {
      const status = await documentService.getDocumentStatus(conversationId, fileId)
      
      // 更新本地缓存
      const docs = documents.value[conversationId] || []
      const index = docs.findIndex(d => d.file_id === fileId)
      if (index !== -1) {
        docs[index] = { ...docs[index], ...status }
      }
      
      return status
    } catch (err) {
      error.value = err
      throw err
    }
  }

  /**
   * 删除文档
   */
  async function deleteDocument(conversationId, fileId) {
    loading.value = true
    error.value = null
    try {
      await documentService.deleteDocument(conversationId, fileId)
      
      // 从列表中移除
      const docs = documents.value[conversationId] || []
      const index = docs.findIndex(d => d.file_id === fileId)
      if (index !== -1) {
        docs.splice(index, 1)
      }
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取文档的幻灯片列表
   */
  async function getDocumentSlides(conversationId, fileId) {
    try {
      return await documentService.getDocumentSlides(conversationId, fileId)
    } catch (err) {
      error.value = err
      throw err
    }
  }

  /**
   * 获取单个幻灯片
   */
  async function getSlide(conversationId, fileId, slideId) {
    try {
      return await documentService.getSlide(conversationId, fileId, slideId)
    } catch (err) {
      error.value = err
      throw err
    }
  }

  /**
   * 开始监控知识提取进度
   * @param {string} conversationId - 对话ID
   * @param {Array} uploadedFiles - 上传的文件列表 [{ file_id, filename }]
   */
  function startExtractionProgress(conversationId, uploadedFiles) {
    // 停止之前的轮询（如果存在）
    stopExtractionProgress(conversationId)
    
    // 初始化进度状态
    if (!extractionProgress.value[conversationId]) {
      extractionProgress.value[conversationId] = {}
    }
    
    // 为每个文件初始化进度
    uploadedFiles.forEach(file => {
      extractionProgress.value[conversationId][file.file_id] = {
        fileName: file.filename,
        status: 'pending',
        progress: 0,
        error: null
      }
    })
    
    // 立即执行一次检查
    checkExtractionProgress(conversationId, uploadedFiles)
    
    // 设置轮询定时器（5秒间隔）
    const timerId = setInterval(() => {
      checkExtractionProgress(conversationId, uploadedFiles)
    }, 5000)
    
    extractionPollingTimers.value[conversationId] = timerId
  }
  
  /**
   * 检查知识提取进度
   * @param {string} conversationId - 对话ID
   * @param {Array} uploadedFiles - 文件列表
   */
  async function checkExtractionProgress(conversationId, uploadedFiles) {
    if (!extractionProgress.value[conversationId]) {
      return
    }
    
    for (const file of uploadedFiles) {
      const fileId = file.file_id
      
      try {
        const status = await getDocumentStatus(conversationId, fileId)
        
        // 更新进度状态
        const currentProgress = extractionProgress.value[conversationId][fileId]
        if (currentProgress) {
          // 优先使用后端返回的真实进度信息
          if (status.progress && status.status === 'processing') {
            // 使用后端返回的进度
            currentProgress.progress = Math.round(status.progress.percentage || 0)
            currentProgress.status = 'processing'
            currentProgress.stage = status.progress.stage || null
            currentProgress.current = status.progress.current || 0
            currentProgress.total = status.progress.total || 0
          } else {
            // 根据状态计算进度（回退方案）
            let progress = 0
            let statusText = 'pending'
            
            switch (status.status) {
              case 'pending':
                progress = 0
                statusText = 'pending'
                break
              case 'processing':
                progress = 50 // 处理中设为50%（如果后端没有返回进度）
                statusText = 'processing'
                break
              case 'completed':
                progress = 100
                statusText = 'completed'
                break
              case 'failed':
                progress = 0
                statusText = 'failed'
                break
              default:
                progress = 0
                statusText = status.status || 'unknown'
            }
            
            currentProgress.progress = progress
            currentProgress.status = statusText
            currentProgress.stage = null
            currentProgress.current = 0
            currentProgress.total = 0
          }
          
          currentProgress.error = status.error || null
        }
      } catch (err) {
        console.error(`检查文件 ${fileId} 状态失败:`, err)
        // 不停止轮询，继续检查其他文件
      }
    }
    
    // 检查是否所有文件都已完成或失败
    const remaining = Object.values(extractionProgress.value[conversationId] || {})
      .filter(item => item.status !== 'completed' && item.status !== 'failed')
    
    // 如果所有文件都已完成或失败，停止轮询
    if (remaining.length === 0) {
      stopExtractionProgress(conversationId)
    }
  }
  
  /**
   * 停止监控知识提取进度
   * @param {string} conversationId - 对话ID
   */
  function stopExtractionProgress(conversationId) {
    if (extractionPollingTimers.value[conversationId]) {
      clearInterval(extractionPollingTimers.value[conversationId])
      delete extractionPollingTimers.value[conversationId]
    }
  }
  
  /**
   * 获取指定对话的提取进度列表
   * @param {string} conversationId - 对话ID
   * @returns {Array} 提取进度列表
   */
  function getExtractionProgress(conversationId) {
    if (!conversationId || !extractionProgress.value[conversationId]) {
      return []
    }
    
    return Object.entries(extractionProgress.value[conversationId]).map(([fileId, progress]) => ({
      fileId,
      ...progress
    }))
  }
  
  /**
   * 清空指定对话的文档
   */
  function clearDocuments(conversationId) {
    if (conversationId) {
      delete documents.value[conversationId]
      // 停止该对话的提取进度监控
      stopExtractionProgress(conversationId)
      delete extractionProgress.value[conversationId]
    } else {
      documents.value = {}
      // 停止所有轮询
      Object.keys(extractionPollingTimers.value).forEach(id => {
        stopExtractionProgress(id)
      })
      extractionProgress.value = {}
      extractionPollingTimers.value = {}
    }
  }
  
  /**
   * 清理指定文件的提取进度
   * @param {string} conversationId - 对话ID
   * @param {string} fileId - 文件ID
   */
  function removeExtractionProgress(conversationId, fileId) {
    if (extractionProgress.value[conversationId] && extractionProgress.value[conversationId][fileId]) {
      delete extractionProgress.value[conversationId][fileId]
      
      // 如果该对话没有正在处理的文件了，停止轮询
      const remaining = Object.values(extractionProgress.value[conversationId] || {})
        .filter(item => item.status !== 'completed' && item.status !== 'failed')
      
      if (remaining.length === 0) {
        stopExtractionProgress(conversationId)
      }
    }
  }

  /**
   * 重置状态
   */
  function reset() {
    documents.value = {}
    uploading.value = false
    loading.value = false
    error.value = null
  }

  return {
    // 状态
    documents,
    uploading,
    uploadProgress,
    uploadingFileName,
    loading,
    error,
    extractionProgress,
    // 计算属性
    getDocumentsByConversation,
    getDocumentCount,
    // Actions
    uploadDocuments,
    loadDocuments,
    getDocument,
    getDocumentStatus,
    deleteDocument,
    getDocumentSlides,
    getSlide,
    getExtractionProgress,
    startExtractionProgress,
    stopExtractionProgress,
    removeExtractionProgress,
    clearDocuments,
    reset
  }
})

