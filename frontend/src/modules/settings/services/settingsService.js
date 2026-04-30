import { api } from '../../../services/api'

const API_BASE = '/api/settings'

export const settingsService = {
  async getLLMConfig() {
    return await api.get(`${API_BASE}/llm-config`)
  },

  async updateLLMConfig(scene, config) {
    return await api.post(`${API_BASE}/llm-config/${scene}`, config)
  },

  async updateProviderAPIKey(binding, apiKey) {
    return await api.post(`${API_BASE}/providers/${binding}/api-key`, {
      api_key: apiKey
    })
  },

  async refreshProviderModels(binding) {
    return await api.post(`${API_BASE}/providers/${binding}/models/refresh`)
  },

  async getModelLists() {
    return await api.get(`${API_BASE}/model-lists`)
  }
}
