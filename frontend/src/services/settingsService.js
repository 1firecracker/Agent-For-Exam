/**
 * 设置服务 - API 调用
 */
import { api } from './api'

const API_BASE = '/api/settings'

export const settingsService = {
  /**
   * 获取所有 LLM 配置
   */
  async getLLMConfig() {
    return await api.get(`${API_BASE}/llm-config`)
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
    return await api.post(`${API_BASE}/llm-config/${scene}`, config)
  },

  /**
   * 更新统一服务商 API Key
   */
  async updateProviderAPIKey(binding, apiKey) {
    return await api.post(`${API_BASE}/providers/${binding}/api-key`, {
      api_key: apiKey
    })
  },

  /**
   * 刷新服务商模型列表
   */
  async refreshProviderModels(binding) {
    return await api.post(`${API_BASE}/providers/${binding}/models/refresh`)
  },

  /**
   * 获取支持的模型列表
   */
  async getModelLists() {
    return await api.get(`${API_BASE}/model-lists`)
  }
}
