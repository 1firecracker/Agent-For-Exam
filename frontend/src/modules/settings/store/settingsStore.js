import { defineStore } from 'pinia'
import { ref } from 'vue'
import { settingsService } from '../services/settingsService'

export const useSettingsStore = defineStore('settings', () => {
  const configs = ref({
    knowledge_graph: {
      binding: 'openai',
      model: '',
      host: ''
    },
    chat: {
      binding: 'openai',
      model: '',
      host: ''
    },
    mindmap: {
      binding: 'openai',
      model: '',
      host: ''
    },
    embedding: {
      binding: 'siliconflow',
      model: '',
      host: ''
    },
    ocr: {
      binding: 'siliconflow',
      model: '',
      host: ''
    }
  })
  
  const modelLists = ref({
    siliconflow: []
  })

  const providers = ref({
    siliconflow: {
      has_api_key: false,
      host: 'https://api.siliconflow.cn/v1',
      last_synced_at: '',
      last_error: ''
    }
  })
  
  const loading = ref(false)

  async function loadConfig() {
    loading.value = true
    try {
      const data = await settingsService.getLLMConfig()
      configs.value = {
        knowledge_graph: data.knowledge_graph,
        chat: data.chat,
        mindmap: data.mindmap,
        embedding: data.embedding || { binding: 'siliconflow', model: '', host: '' },
        ocr: data.ocr || { binding: 'siliconflow', model: '', host: '' }
      }
      modelLists.value = data.model_lists || {}
      providers.value = data.providers || providers.value
    } catch (error) {
      console.error('加载配置失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function updateConfig(scene, config) {
    loading.value = true
    try {
      const result = await settingsService.updateLLMConfig(scene, config)
      configs.value[scene] = result.config
      // 如果返回了更新的模型列表，更新本地模型列表
      if (result.model_lists) {
        modelLists.value = result.model_lists
      }
      if (result.providers) {
        providers.value = result.providers
      }
      return result
    } catch (error) {
      console.error('更新配置失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function updateProviderAPIKey(binding, apiKey) {
    loading.value = true
    try {
      const result = await settingsService.updateProviderAPIKey(binding, apiKey)
      if (result.model_lists) {
        modelLists.value = result.model_lists
      }
      if (result.providers) {
        providers.value = result.providers
      }
      return result
    } catch (error) {
      console.error('更新统一 API Key 失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function refreshProviderModels(binding) {
    loading.value = true
    try {
      const result = await settingsService.refreshProviderModels(binding)
      if (result.model_lists) {
        modelLists.value = result.model_lists
      }
      if (result.providers) {
        providers.value = result.providers
      }
      return result
    } catch (error) {
      console.error('刷新模型列表失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  return {
    configs,
    modelLists,
    providers,
    loading,
    loadConfig,
    updateConfig,
    updateProviderAPIKey,
    refreshProviderModels
  }
})

