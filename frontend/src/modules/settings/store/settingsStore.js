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
    }
  })
  
  const modelLists = ref({
    siliconflow: []
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
        embedding: data.embedding || { binding: 'siliconflow', model: '', host: '' }
      }
      modelLists.value = data.model_lists || {}
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
      return result
    } catch (error) {
      console.error('更新配置失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  return {
    configs,
    modelLists,
    loading,
    loadConfig,
    updateConfig
  }
})


