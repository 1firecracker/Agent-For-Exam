/**
 * 设置服务 - API 调用
 */
import axios from 'axios'

const API_BASE = '/api/settings'

export const settingsService = {
  /**
   * 获取所有 LLM 配置
   */
  async getLLMConfig() {
    const response = await axios.get(`${API_BASE}/llm-config`)
    return response.data
  },

  /**
   * 更新指定场景的 LLM 配置
   * @param {string} scene - 场景名称（knowledge_graph, chat, mindmap）
   * @param {object} config - 配置对象
   * @param {string} config.binding - 服务商（openai, siliconflow）
   * @param {string} config.model - 模型名称
   * @param {string} config.host - API 地址
   * @param {string} [config.api_key] - API Key（可选）
   */
  async updateLLMConfig(scene, config) {
    const response = await axios.post(`${API_BASE}/llm-config/${scene}`, config)
    return response.data
  },

  /**
   * 获取支持的模型列表
   */
  async getModelLists() {
    const response = await axios.get(`${API_BASE}/model-lists`)
    return response.data
  }
}

