import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import mindmapService from '../services/mindmapService'

export const useMindMapStore = defineStore('mindmap', () => {
  const mindmapContent = ref('')
  const loading = ref(false)
  const generating = ref(false)
  const error = ref(null)
  const conversationId = ref(null)

  const hasMindMap = computed(() => {
    return mindmapContent.value && mindmapContent.value.trim().length > 0
  })

  async function loadMindMap(convId) {
    if (!convId) {
      mindmapContent.value = ''
      conversationId.value = null
      return
    }

    conversationId.value = convId
    loading.value = true
    error.value = null

    try {
      const response = await mindmapService.getMindMap(convId)
      if (response.exists && response.content) {
        mindmapContent.value = response.content
      } else {
        mindmapContent.value = ''
      }
    } catch (err) {
      error.value = err
      console.error('加载思维脑图失败:', err)
      mindmapContent.value = ''
    } finally {
      loading.value = false
    }
  }

  async function generateMindMap(convId, documentId = null, onProgress = null) {
    conversationId.value = convId
    generating.value = true
    error.value = null
    
    if (!mindmapContent.value) {
      mindmapContent.value = ''
    }

    try {
      let accumulatedContent = ''
      let hasValidContent = false
      let chunkCount = 0

      console.log('📡 开始流式生成，对话ID:', convId, '文档ID:', documentId)
      
      await mindmapService.generateMindMapStream(
        convId,
        documentId,
        (chunk) => {
          chunkCount++
          if (chunkCount % 20 === 0 || chunkCount <= 5) {
            console.log(`📦 收到第 ${chunkCount} 个 chunk，长度: ${chunk.length}`)
          }
          
          accumulatedContent += chunk
          
          let shouldExtract = false
          if (accumulatedContent.length > 50) {
            shouldExtract = true
          } else if (accumulatedContent.includes('##') || accumulatedContent.includes('#') || accumulatedContent.includes('-')) {
            shouldExtract = true
          }
          
          if (shouldExtract) {
            const extracted = extractMindMapContent(accumulatedContent)
            if (extracted) {
              mindmapContent.value = extracted
              hasValidContent = true
              if (chunkCount % 20 === 0 || chunkCount <= 5) {
                console.log(`✅ 提取成功，内容长度: ${extracted.length}`)
              }
            } else {
              let cleaned = accumulatedContent
                .replace(/^```mindmap\s*\n?/i, '')
                .replace(/```\s*$/g, '')
                .trim()
              
              if (cleaned && (cleaned.includes('##') || cleaned.includes('#') || cleaned.includes('-'))) {
                mindmapContent.value = cleaned
                hasValidContent = true
              }
            }
          }
          
          if (onProgress && (chunkCount % 10 === 0 || chunkCount <= 5)) {
            onProgress(mindmapContent.value)
          }
        }
      )

      const finalContent = extractMindMapContent(accumulatedContent)
      if (finalContent) {
        mindmapContent.value = finalContent
        hasValidContent = true
      } else if (accumulatedContent) {
        let cleaned = accumulatedContent
          .replace(/^```mindmap\s*\n?/i, '')
          .replace(/```\s*$/g, '')
          .trim()
        if (cleaned) {
          mindmapContent.value = cleaned
          hasValidContent = true
        }
      }
      
      if (!hasValidContent && accumulatedContent.length > 0) {
        console.warn('⚠️ 流式生成完成，但无法提取有效内容，原始内容长度:', accumulatedContent.length)
      }
    } catch (err) {
      error.value = err
      console.error('生成思维脑图失败:', err)
      throw err
    } finally {
      generating.value = false
    }
  }

  function extractMindMapContent(text) {
    if (!text || !text.trim()) return null

    if (text.length < 10 && !text.includes('#') && !text.includes('-') && !text.includes('*')) {
      return null
    }

    const codeBlockPattern = /```mindmap\s*\n([\s\S]*?)\n```/
    const match = text.match(codeBlockPattern)
    if (match && match[1]) {
      return match[1].trim()
    }

    const codeBlockStartPattern = /```mindmap\s*\n([\s\S]*)/
    const startMatch = text.match(codeBlockStartPattern)
    if (startMatch && startMatch[1]) {
      let content = startMatch[1].replace(/```\s*$/g, '').trim()
      if (content && (content.includes('#') || content.includes('-') || content.includes('*'))) {
        return content
      }
    }

    if (text.includes('##')) {
      const lines = text.split('\n')
      const mindmapLines = []
      let foundFirstHeader = false

      for (const line of lines) {
        const trimmedLine = line.trim()
        if (trimmedLine.startsWith('##')) {
          foundFirstHeader = true
        }
        if (foundFirstHeader || trimmedLine) {
          mindmapLines.push(line)
        }
      }

      if (mindmapLines.length > 0) {
        return mindmapLines.join('\n').trim()
      }
    }

    if (text.includes('#') || text.includes('-') || text.includes('*')) {
      let cleaned = text
        .replace(/^```mindmap\s*\n?/i, '')
        .replace(/```\s*$/g, '')
        .trim()
      
      if (cleaned && (cleaned.includes('#') || cleaned.includes('-') || cleaned.includes('*'))) {
        return cleaned
      }
    }

    return null
  }

  function clearMindMap() {
    conversationId.value = null
    error.value = null
    loading.value = false
    generating.value = false
  }

  function reset() {
    mindmapContent.value = ''
    loading.value = false
    generating.value = false
    error.value = null
    conversationId.value = null
  }

  return {
    mindmapContent,
    loading,
    generating,
    error,
    conversationId,
    hasMindMap,
    loadMindMap,
    generateMindMap,
    clearMindMap,
    reset
  }
})


