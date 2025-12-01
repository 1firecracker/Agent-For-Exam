import { api } from './api'

/**
 * 思维脑图服务
 */
class MindMapService {
  /**
   * 获取对话的思维脑图
   * @param {string} conversationId - 对话ID
   * @returns {Promise<Object>} 思维脑图内容
   */
  async getMindMap(conversationId) {
    const response = await api.get(`/api/conversations/${conversationId}/mindmap`)
    return response
  }

  /**
   * 生成思维脑图（流式）
   * @param {string} conversationId - 对话ID
   * @param {string} documentId - 文档ID（可选）
   * @param {Function} onChunk - 流式数据回调 (chunk: string) => void
   * @returns {Promise<void>}
   */
  async generateMindMapStream(conversationId, documentId = null, onChunk) {
    const url = `/api/conversations/${conversationId}/mindmap/generate${documentId ? `?document_id=${documentId}` : ''}`
    
    console.log('📡 发起流式生成请求:', url)
    
    const response = await fetch(`${api.defaults.baseURL}${url}`, {
      method: 'POST',
      headers: {
        'Accept': 'text/event-stream',
      },
    })

    console.log('📡 流式生成响应状态:', response.status, response.statusText)

    if (!response.ok) {
      const error = await response.json()
      console.error('❌ 流式生成请求失败:', error)
      throw new Error(error.detail || '生成思维脑图失败')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let lineCount = 0
    let chunkCount = 0

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          console.log('📡 流式生成完成，共收到', chunkCount, '个chunk')
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          lineCount++
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') {
              console.log('📡 收到 [DONE] 信号')
              return
            }
            if (onChunk && data) {
              chunkCount++
              if (chunkCount % 10 === 0 || chunkCount <= 5) {
                console.log(`📦 处理第 ${chunkCount} 个数据块，长度: ${data.length}`)
              }
              onChunk(data)
            }
          }
        }
      }
    } catch (error) {
      console.error('❌ 流式读取错误:', error)
      throw error
    } finally {
      reader.releaseLock()
      console.log('🔒 释放 reader 锁')
    }
  }

  /**
   * 删除思维脑图
   * @param {string} conversationId - 对话ID
   * @returns {Promise<void>}
   */
  async deleteMindMap(conversationId) {
    await api.delete(`/api/conversations/${conversationId}/mindmap`)
  }
}

export default new MindMapService()

