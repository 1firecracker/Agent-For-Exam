import axios from 'axios'

const API_BASE = '/api/settings'

export const settingsService = {
  async getLLMConfig() {
    const response = await axios.get(`${API_BASE}/llm-config`)
    return response.data
  },

  async updateLLMConfig(scene, config) {
    const response = await axios.post(`${API_BASE}/llm-config/${scene}`, config)
    return response.data
  },

  async updateProviderAPIKey(binding, apiKey) {
    const response = await axios.post(`${API_BASE}/providers/${binding}/api-key`, {
      api_key: apiKey
    })
    return response.data
  },

  async refreshProviderModels(binding) {
    const response = await axios.post(`${API_BASE}/providers/${binding}/models/refresh`)
    return response.data
  },

  async getModelLists() {
    const response = await axios.get(`${API_BASE}/model-lists`)
    return response.data
  }
}

