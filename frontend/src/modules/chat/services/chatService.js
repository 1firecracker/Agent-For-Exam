import { api } from '../../../services/api'

class ChatService {
  async queryStream(conversationId, query, mode = 'naive', agentIntent, onChunk) {
    const body = {
      query,
      mode,
      stream: true
    }
    
    if (agentIntent) {
      // 预留扩展
    }
    
    const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    const response = await fetch(`${base}/api/conversations/${conversationId}/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body)
    })
    
    if (!response.ok) {
      throw new Error(`查询失败: ${response.statusText}`)
    }
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    
    while (true) {
      const { done, value } = await reader.read()
      
      if (done) {
        break
      }
      
      buffer += decoder.decode(value, { stream: true })
      
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        if (line.trim()) {
          try {
            const parsed = JSON.parse(line)
            
            if (parsed.response !== undefined) {
              if (typeof parsed.response === 'string') {
                onChunk({ type: 'response', content: parsed.response })
              } else if (parsed.response && typeof parsed.response === 'object') {
                onChunk(parsed.response)
              } else {
                onChunk({ type: 'response', content: String(parsed.response) })
              }
            } else if (parsed.warning) {
              onChunk({ type: 'warning', content: parsed.warning })
            } else if (parsed.tool_call) {
              onChunk({ type: 'tool_call', tool_call: parsed.tool_call })
            } else if (parsed.tool_result) {
              onChunk({ type: 'tool_result', tool_result: parsed.tool_result })
            } else if (parsed.tool_error) {
              onChunk({ type: 'tool_error', ...parsed.tool_error })
            } else if (parsed.mindmap_content) {
              onChunk({ type: 'mindmap_content', content: parsed.mindmap_content })
            } else if (parsed.error) {
              onChunk({ type: 'error', content: parsed.error })
            }
          } catch (error) {
            console.error('解析流式响应失败:', line, error)
          }
        }
      }
    }
    
    if (buffer.trim()) {
      try {
        const parsed = JSON.parse(buffer)
        if (parsed.response) {
          onChunk(parsed.response)
        } else if (parsed.warning) {
          onChunk({ type: 'warning', content: parsed.warning })
        }
      } catch (error) {
        console.error('解析最终数据块失败:', buffer, error)
      }
    }
  }
  
  async getHistory(conversationId) {
    const response = await api.get(`/api/conversations/${conversationId}/messages`)
    return response
  }
  
  async saveMessage(conversationId, query, answer, toolCalls = null, streamItems = null) {
    await api.post(`/api/conversations/${conversationId}/messages`, {
      query,
      answer,
      tool_calls: toolCalls,
      stream_items: streamItems
    })
  }
}

export default new ChatService()


