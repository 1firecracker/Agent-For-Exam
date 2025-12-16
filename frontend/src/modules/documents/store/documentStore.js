import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import documentService from '../services/documentService'

export const useDocumentStore = defineStore('document', () => {
  const documents = ref({})
  const uploading = ref(false)
  const uploadProgress = ref(0)
  const uploadingFileName = ref('')
  const loading = ref(false)
  const error = ref(null)

  const extractionProgress = ref({})
  const extractionPollingTimers = ref({})

  const getDocumentsByConversation = computed(() => {
    return (conversationId) => {
      return documents.value[conversationId] || []
    }
  })

  const getDocumentCount = computed(() => {
    return (conversationId) => {
      return documents.value[conversationId]?.length || 0
    }
  })

  async function uploadDocuments(conversationId, files, onProgress) {
    uploading.value = true
    uploadProgress.value = 0
    error.value = null
    
    const fileArray = Array.isArray(files) ? files : [files]
    uploadingFileName.value = fileArray.length === 1 ? fileArray[0].name : `${fileArray.length} 个文件`
    
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
      
      uploadProgress.value = 100
      
      const resultConversationId = response.conversation_id
      
      if (resultConversationId) {
        await loadDocuments(resultConversationId)
      }
      
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
      setTimeout(() => {
        uploadProgress.value = 0
      }, 500)
    }
  }

  async function loadDocuments(conversationId) {
    loading.value = true
    error.value = null
    try {
      const response = await documentService.getDocuments(conversationId)
      documents.value[conversationId] = response.documents || []
      
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

  async function getDocument(conversationId, fileId) {
    try {
      const document = await documentService.getDocument(conversationId, fileId)
      
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

  async function getDocumentStatus(conversationId, fileId) {
    try {
      const status = await documentService.getDocumentStatus(conversationId, fileId)
      
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

  async function deleteDocument(conversationId, fileId) {
    loading.value = true
    error.value = null
    try {
      await documentService.deleteDocument(conversationId, fileId)
      
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

  async function getDocumentSlides(conversationId, fileId) {
    try {
      return await documentService.getDocumentSlides(conversationId, fileId)
    } catch (err) {
      error.value = err
      throw err
    }
  }

  async function getSlide(conversationId, fileId, slideId) {
    try {
      return await documentService.getSlide(conversationId, fileId, slideId)
    } catch (err) {
      error.value = err
      throw err
    }
  }

  function startExtractionProgress(conversationId, uploadedFiles) {
    stopExtractionProgress(conversationId)
    
    if (!extractionProgress.value[conversationId]) {
      extractionProgress.value[conversationId] = {}
    }
    
    uploadedFiles.forEach(file => {
      extractionProgress.value[conversationId][file.file_id] = {
        fileName: file.filename,
        status: 'pending',
        progress: 0,
        error: null
      }
    })
    
    checkExtractionProgress(conversationId, uploadedFiles)
    
    const timerId = setInterval(() => {
      checkExtractionProgress(conversationId, uploadedFiles)
    }, 5000)
    
    extractionPollingTimers.value[conversationId] = timerId
  }
  
  async function checkExtractionProgress(conversationId, uploadedFiles) {
    if (!extractionProgress.value[conversationId]) {
      return
    }
    
    for (const file of uploadedFiles) {
      const fileId = file.file_id
      
      try {
        const status = await getDocumentStatus(conversationId, fileId)
        
        const currentProgress = extractionProgress.value[conversationId][fileId]
        if (currentProgress) {
          if (status.progress && status.status === 'processing') {
            currentProgress.progress = Math.round(status.progress.percentage || 0)
            currentProgress.status = 'processing'
            currentProgress.stage = status.progress.stage || null
            currentProgress.current = status.progress.current || 0
            currentProgress.total = status.progress.total || 0
          } else {
            let progress = 0
            let statusText = 'pending'
            
            switch (status.status) {
              case 'pending':
                progress = 0
                statusText = 'pending'
                break
              case 'processing':
                progress = 50
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
      }
    }
    
    const remaining = Object.values(extractionProgress.value[conversationId] || {})
      .filter(item => item.status !== 'completed' && item.status !== 'failed')
    
    if (remaining.length === 0) {
      stopExtractionProgress(conversationId)
    }
  }
  
  function stopExtractionProgress(conversationId) {
    if (extractionPollingTimers.value[conversationId]) {
      clearInterval(extractionPollingTimers.value[conversationId])
      delete extractionPollingTimers.value[conversationId]
    }
  }
  
  function getExtractionProgress(conversationId) {
    if (!conversationId || !extractionProgress.value[conversationId]) {
      return []
    }
    
    return Object.entries(extractionProgress.value[conversationId]).map(([fileId, progress]) => ({
      fileId,
      ...progress
    }))
  }
  
  function clearDocuments(conversationId) {
    if (conversationId) {
      delete documents.value[conversationId]
      stopExtractionProgress(conversationId)
      delete extractionProgress.value[conversationId]
    } else {
      documents.value = {}
      Object.keys(extractionPollingTimers.value).forEach(id => {
        stopExtractionProgress(id)
      })
      extractionProgress.value = {}
      extractionPollingTimers.value = {}
    }
  }
  
  function removeExtractionProgress(conversationId, fileId) {
    if (extractionProgress.value[conversationId] && extractionProgress.value[conversationId][fileId]) {
      delete extractionProgress.value[conversationId][fileId]
      
      const remaining = Object.values(extractionProgress.value[conversationId] || {})
        .filter(item => item.status !== 'completed' && item.status !== 'failed')
      
      if (remaining.length === 0) {
        stopExtractionProgress(conversationId)
      }
    }
  }

  function reset() {
    documents.value = {}
    uploading.value = false
    loading.value = false
    error.value = null
  }

  return {
    documents,
    uploading,
    uploadProgress,
    uploadingFileName,
    loading,
    error,
    extractionProgress,
    getDocumentsByConversation,
    getDocumentCount,
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


