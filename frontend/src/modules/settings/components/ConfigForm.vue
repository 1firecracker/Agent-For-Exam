<template>
  <el-form :model="localConfig" label-width="120px" label-position="left">
    <el-form-item label="模型">
      <el-select
        v-model="localConfig.model"
        filterable
        allow-create
        default-first-option
        :reserve-keyword="false"
        placeholder="选择或输入模型名称"
        style="width: 100%"
        @change="handleModelChange"
      >
        <el-option
          v-for="model in availableModels"
          :key="model"
          :label="model"
          :value="model"
        />
      </el-select>
      <div class="form-tip">可以从列表选择，也可以手动输入自定义模型名称</div>
    </el-form-item>

    <el-form-item label="API Key">
      <el-input
        v-model="localConfig.api_key"
        type="password"
        show-password
        placeholder="输入 API Key（留空则不更新）"
        @blur="handleApiKeyChange"
      />
      <div class="form-tip">留空则保留原有 API Key，输入新值则更新</div>
    </el-form-item>

    <el-form-item>
      <el-button type="primary" @click="handleSave" :loading="saving">
        保存配置
      </el-button>
    </el-form-item>
  </el-form>
</template>

<script setup>
import { ref, watch, computed } from 'vue'

const props = defineProps({
  config: {
    type: Object,
    required: true
  },
  modelLists: {
    type: Object,
    default: () => ({})
  },
  defaultBinding: {
    type: String,
    default: 'siliconflow'
  }
})

const emit = defineEmits(['update'])

const localConfig = ref({
  binding: props.defaultBinding,
  model: '',
  api_key: ''
})

const saving = ref(false)

const availableModels = computed(() => {
  return props.modelLists['siliconflow'] || []
})

watch(() => props.config, (newConfig) => {
  if (newConfig) {
    localConfig.value = {
      binding: newConfig.binding || props.defaultBinding,
      model: newConfig.model || '',
      api_key: ''
    }
  }
}, { immediate: true })

function handleModelChange() {
}

function handleApiKeyChange() {
}

function handleSave() {
  saving.value = true
  
  const updateData = {
    binding: localConfig.value.binding || props.defaultBinding,
    model: localConfig.value.model,
    host: 'https://api.siliconflow.cn/v1'
  }
  
  if (localConfig.value.api_key && localConfig.value.api_key.trim()) {
    updateData.api_key = localConfig.value.api_key
  }
  
  emit('update', updateData)
  
  localConfig.value.api_key = ''
  
  saving.value = false
}
</script>

<style scoped>
.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>


