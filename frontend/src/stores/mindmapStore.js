import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import mindmapService from '../services/mindmapService'

export const useMindMapStore = defineStore('mindmap', () => {
  // 状态
  const mindmapContent = ref('') // 当前思维脑图内容
  const loading = ref(false)
  const generating = ref(false) // 是否正在生成
  const error = ref(null)
  const conversationId = ref(null) // 当前对话ID

  // 计算属性
  const hasMindMap = computed(() => {
    return mindmapContent.value && mindmapContent.value.trim().length > 0
  })

  // Actions
  /**
   * 加载思维脑图
   * @param {string} convId - 对话ID
   */
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

  /**
   * 生成思维脑图（流式）
   * @param {string} convId - 对话ID
   * @param {string} documentId - 文档ID（可选）
   * @param {Function} onProgress - 进度回调 (content: string) => void
   */
  async function generateMindMap(convId, documentId = null, onProgress = null) {
    conversationId.value = convId
    generating.value = true
    error.value = null
    
    // 注意：不清空旧内容，支持增量更新（多个文档合并）
    // 如果这是第一个文档，内容为空，则清空；否则保留已有内容
    if (!mindmapContent.value) {
      mindmapContent.value = ''
    }

    try {
      let accumulatedContent = ''
      let hasValidContent = false // 标记是否收到有效内容
      let chunkCount = 0 // 统计收到的 chunk 数量

      console.log('📡 开始流式生成，对话ID:', convId, '文档ID:', documentId)
      
      await mindmapService.generateMindMapStream(
        convId,
        documentId,
        (chunk) => {
          chunkCount++
          if (chunkCount % 20 === 0 || chunkCount <= 5) {
            console.log(`📦 收到第 ${chunkCount} 个 chunk，长度: ${chunk.length}`)
          }
          
          // 直接累加原始内容（不等待提取）
          accumulatedContent += chunk
          
          // 实时更新内容（支持流式渲染）
          // 优先尝试提取完整内容（优化：只在内容足够长或包含关键标记时提取）
          let shouldExtract = false
          if (accumulatedContent.length > 50) {
            // 内容足够长，尝试提取
            shouldExtract = true
          } else if (accumulatedContent.includes('##') || accumulatedContent.includes('#') || accumulatedContent.includes('-')) {
            // 包含 markdown 标记，尝试提取
            shouldExtract = true
          }
          
          if (shouldExtract) {
            const extracted = extractMindMapContent(accumulatedContent)
            if (extracted) {
              // 如果提取成功，使用提取的内容
              mindmapContent.value = extracted
              hasValidContent = true
              if (chunkCount % 20 === 0 || chunkCount <= 5) {
                console.log(`✅ 提取成功，内容长度: ${extracted.length}`)
              }
            } else {
              // 如果提取失败，尝试快速清理后使用（流式过程中的部分内容）
              // 只做简单的清理，不进行复杂提取
              let cleaned = accumulatedContent
                .replace(/^```mindmap\s*\n?/i, '')
                .replace(/```\s*$/g, '')
                .trim()
              
              // 如果清理后的内容包含 markdown 格式，直接使用
              if (cleaned && (cleaned.includes('##') || cleaned.includes('#') || cleaned.includes('-'))) {
                mindmapContent.value = cleaned
                hasValidContent = true
              }
            }
          }
          
          // 进度回调（减少调用频率）
          if (onProgress && (chunkCount % 10 === 0 || chunkCount <= 5)) {
            onProgress(mindmapContent.value)
          }
        }
      )

      // 流式结束，最终提取（确保使用完整内容）
      const finalContent = extractMindMapContent(accumulatedContent)
      if (finalContent) {
        mindmapContent.value = finalContent
        hasValidContent = true
      } else if (accumulatedContent) {
        // 如果最终提取失败，尝试清理后使用
        let cleaned = accumulatedContent
          .replace(/^```mindmap\s*\n?/i, '')
          .replace(/```\s*$/g, '')
          .trim()
        if (cleaned) {
          mindmapContent.value = cleaned
          hasValidContent = true
        }
      }
      
      // 如果流式生成完成但没有有效内容，记录警告
      if (!hasValidContent && accumulatedContent.length > 0) {
        console.warn('⚠️ 流式生成完成，但无法提取有效内容，原始内容长度:', accumulatedContent.length)
      }
    } catch (err) {
      error.value = err
      console.error('生成思维脑图失败:', err)
      throw err // 重新抛出错误，让调用者知道生成失败
    } finally {
      generating.value = false
    }
  }

  /**
   * 从文本中提取 mindmap 代码块内容（支持流式部分内容，优化性能）
   * @param {string} text - 原始文本
   * @returns {string|null} 提取的 mindmap 内容
   */
  function extractMindMapContent(text) {
    if (!text || !text.trim()) return null

    // 快速检查：如果文本太短且不包含任何 markdown 标记，直接返回 null
    if (text.length < 10 && !text.includes('#') && !text.includes('-') && !text.includes('*')) {
      return null
    }

    // 1. 优先匹配完整的 ```mindmap ... ``` 代码块
    const codeBlockPattern = /```mindmap\s*\n([\s\S]*?)\n```/
    const match = text.match(codeBlockPattern)
    if (match && match[1]) {
      return match[1].trim()
    }

    // 2. 如果代码块未完整，尝试提取代码块开始后的内容（流式场景）
    const codeBlockStartPattern = /```mindmap\s*\n([\s\S]*)/
    const startMatch = text.match(codeBlockStartPattern)
    if (startMatch && startMatch[1]) {
      // 移除可能的 ``` 结尾（如果存在但不完整）
      let content = startMatch[1].replace(/```\s*$/g, '').trim()
      // 如果内容包含 markdown 格式，直接返回（流式场景）
      if (content && (content.includes('#') || content.includes('-') || content.includes('*'))) {
        return content
      }
    }

    // 3. 如果没有代码块标记，检查是否包含 ## 标记（一级节点）
    if (text.includes('##')) {
      const lines = text.split('\n')
      const mindmapLines = []
      let foundFirstHeader = false

      for (const line of lines) {
        const trimmedLine = line.trim()
        if (trimmedLine.startsWith('##')) {
          foundFirstHeader = true
        }
        // 从第一个标题开始收集，或收集所有非空行（流式场景）
        if (foundFirstHeader || trimmedLine) {
          mindmapLines.push(line)
        }
      }

      if (mindmapLines.length > 0) {
        return mindmapLines.join('\n').trim()
      }
    }

    // 4. 如果以上都不匹配，但文本包含 markdown 格式的内容，尝试直接返回（流式场景）
    // 检查是否包含 markdown 格式的标题或列表
    if (text.includes('#') || text.includes('-') || text.includes('*')) {
      // 移除可能的代码块标记前缀和后缀
      let cleaned = text
        .replace(/^```mindmap\s*\n?/i, '')
        .replace(/```\s*$/g, '')
        .trim()
      
      // 如果清理后的内容仍然包含 markdown 标记，返回它
      if (cleaned && (cleaned.includes('#') || cleaned.includes('-') || cleaned.includes('*'))) {
        return cleaned
      }
    }

    return null
  }

  /**
   * 清空思维脑图（不清空内容，只重置状态）
   */
  function clearMindMap() {
    // 不清空内容，避免刷新时内容消失
    // mindmapContent.value = ''
    conversationId.value = null
    error.value = null
    loading.value = false
    generating.value = false
  }

  /**
   * 重置状态
   */
  function reset() {
    mindmapContent.value = ''
    loading.value = false
    generating.value = false
    error.value = null
    conversationId.value = null
  }

  return {
    // 状态
    mindmapContent,
    loading,
    generating,
    error,
    conversationId,
    // 计算属性
    hasMindMap,
    // Actions
    loadMindMap,
    generateMindMap,
    clearMindMap,
    reset
  }
})

