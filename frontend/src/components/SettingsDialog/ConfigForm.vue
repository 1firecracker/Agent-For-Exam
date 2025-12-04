<template>
  <el-form :model="localConfig" label-width="120px" label-position="left">
    <!-- 模型选择 -->
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

    <!-- API Key -->
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

    <!-- 保存按钮 -->
    <el-form-item>
      <el-button type="primary" @click="handleSave" :loading="saving">
        保存配置
      </el-button>
    </el-form-item>
  </el-form>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  config: {
    type: Object,
    required: true
  },
  modelLists: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update'])

const localConfig = ref({
  binding: 'siliconflow', // 固定为硅基流动
  model: '',
  api_key: ''
})

const saving = ref(false)

// 可用模型列表（固定使用硅基流动）
const availableModels = computed(() => {
  return props.modelLists['siliconflow'] || []
})

// 监听 props.config 变化，同步到本地
watch(() => props.config, (newConfig) => {
  if (newConfig) {
    localConfig.value = {
      binding: 'siliconflow', // 固定为硅基流动
      model: newConfig.model || '',
      api_key: '' // API Key 不显示，需要用户重新输入
    }
  }
}, { immediate: true })

// 模型变化
function handleModelChange() {
  // 可以在这里添加验证逻辑
}

// API Key 变化
function handleApiKeyChange() {
  // 可以在这里添加验证逻辑
}

// 保存配置
function handleSave() {
  saving.value = true
  
  // 构建更新数据（固定使用硅基流动，host 固定为硅基流动地址）
  const updateData = {
    binding: 'siliconflow', // 固定为硅基流动
    model: localConfig.value.model,
    host: 'https://api.siliconflow.cn/v1' // 固定为硅基流动地址
  }
  
  // 只有当 api_key 不为空时才传递
  if (localConfig.value.api_key && localConfig.value.api_key.trim()) {
    updateData.api_key = localConfig.value.api_key
  }
  
  emit('update', updateData)
  
  // 清空 API Key 输入（已保存）
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

