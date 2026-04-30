<template>
  <el-dialog
    v-model="dialogVisible"
    title="LLM 配置设置"
    width="800px"
    class="settings-llm-dialog"
    :before-close="handleClose"
  >
    <section class="provider-panel">
      <div class="provider-header">
        <div>
          <div class="provider-title">统一 API Key</div>
          <div class="provider-meta">
            SiliconFlow
            <el-tag
              size="small"
              :type="providers.siliconflow?.has_api_key ? 'success' : 'warning'"
            >
              {{ providers.siliconflow?.has_api_key ? '已配置' : '未配置' }}
            </el-tag>
          </div>
        </div>
        <el-button size="small" @click="handleRefreshModels" :loading="refreshingModels">
          刷新模型列表
        </el-button>
      </div>

      <el-form label-width="120px" label-position="left">
        <el-form-item label="API Key">
          <el-input
            v-model="providerApiKey"
            type="password"
            show-password
            placeholder="输入 SiliconFlow API Key"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleProviderKeySave" :loading="savingProviderKey">
            保存统一 Key
          </el-button>
          <span class="sync-status" v-if="providers.siliconflow?.last_synced_at">
            上次同步：{{ providers.siliconflow.last_synced_at }}
          </span>
        </el-form-item>
        <div class="sync-error" v-if="providers.siliconflow?.last_error">
          {{ providers.siliconflow.last_error }}
        </div>
      </el-form>
    </section>

    <el-tabs v-model="activeTab">
      <!-- 知识图谱配置 -->
      <el-tab-pane label="知识图谱抽取" name="knowledge_graph">
        <ConfigForm 
          :config="configs.knowledge_graph"
          :model-lists="modelLists"
          @update="handleUpdate('knowledge_graph', $event)"
        />
      </el-tab-pane>
      
      <!-- 聊天配置 -->
      <el-tab-pane label="聊天对话" name="chat">
        <ConfigForm 
          :config="configs.chat"
          :model-lists="modelLists"
          @update="handleUpdate('chat', $event)"
        />
      </el-tab-pane>
      
      <!-- 思维导图配置 -->
      <el-tab-pane label="思维导图生成" name="mindmap">
        <ConfigForm 
          :config="configs.mindmap"
          :model-lists="modelLists"
          @update="handleUpdate('mindmap', $event)"
        />
      </el-tab-pane>
      
      <!-- 嵌入向量配置 -->
      <el-tab-pane label="嵌入向量" name="embedding">
        <ConfigForm 
          :config="configs.embedding"
          :model-lists="modelLists"
          default-binding="siliconflow"
          @update="handleUpdate('embedding', $event)"
        />
      </el-tab-pane>

      <!-- OCR 配置 -->
      <el-tab-pane label="OCR" name="ocr">
        <ConfigForm
          :config="configs.ocr"
          :model-lists="modelLists"
          default-binding="siliconflow"
          @update="handleUpdate('ocr', $event)"
        />
      </el-tab-pane>
    </el-tabs>
    
    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useSettingsStore } from '../stores/settingsStore'
import ConfigForm from './SettingsDialog/ConfigForm.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])

const settingsStore = useSettingsStore()
const dialogVisible = ref(false)
const activeTab = ref('knowledge_graph')
const providerApiKey = ref('')
const savingProviderKey = ref(false)
const refreshingModels = ref(false)

// 计算属性
const configs = computed(() => settingsStore.configs)
const modelLists = computed(() => settingsStore.modelLists)
const providers = computed(() => settingsStore.providers)

// 监听 modelValue 变化
watch(() => props.modelValue, (val) => {
  dialogVisible.value = val
  if (val) {
    loadConfig()
  }
})

// 监听 dialogVisible 变化，同步到父组件
watch(dialogVisible, (val) => {
  emit('update:modelValue', val)
})

// 加载配置
async function loadConfig() {
  try {
    await settingsStore.loadConfig()
  } catch (error) {
    ElMessage.error('加载配置失败: ' + (error.response?.data?.detail || error.message))
  }
}

// 更新配置
async function handleUpdate(scene, config) {
  try {
    await settingsStore.updateConfig(scene, config)
    ElMessage.success('配置已更新并立即生效')
  } catch (error) {
    ElMessage.error('更新配置失败: ' + (error.response?.data?.detail || error.message))
  }
}

async function handleProviderKeySave() {
  if (!providerApiKey.value.trim()) {
    ElMessage.warning('请输入 API Key')
    return
  }

  savingProviderKey.value = true
  try {
    const result = await settingsStore.updateProviderAPIKey('siliconflow', providerApiKey.value)
    providerApiKey.value = ''
    if (result.refresh_error) {
      ElMessage.warning('API Key 已保存，但模型列表刷新失败: ' + result.refresh_error)
    } else {
      ElMessage.success('统一 API Key 已保存，模型列表已刷新')
    }
  } catch (error) {
    ElMessage.error('保存统一 API Key 失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    savingProviderKey.value = false
  }
}

async function handleRefreshModels() {
  refreshingModels.value = true
  try {
    await settingsStore.refreshProviderModels('siliconflow')
    ElMessage.success('模型列表已刷新')
  } catch (error) {
    ElMessage.error('刷新模型列表失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    refreshingModels.value = false
  }
}

// 关闭对话框
function handleClose() {
  dialogVisible.value = false
}

// 组件挂载时加载配置
onMounted(() => {
  if (props.modelValue) {
    loadConfig()
  }
})
</script>

<style scoped>
.provider-panel {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 16px 16px 10px;
  margin-bottom: 16px;
}

.provider-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.provider-title {
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.provider-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #606266;
  font-size: 13px;
}

.sync-status {
  margin-left: 12px;
  color: #909399;
  font-size: 12px;
}

.sync-error {
  color: #f56c6c;
  font-size: 12px;
  margin: -4px 0 8px 120px;
  word-break: break-word;
}

@media (max-width: 768px) {
  .provider-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  .provider-panel {
    padding: 12px;
  }
  .sync-error {
    margin-left: 0;
  }
  .sync-status {
    margin-left: 0;
    display: block;
    margin-top: 4px;
  }

  .settings-llm-dialog {
    width: 95% !important;
    max-width: 95vw !important;
    margin: 5vh auto !important;
  }
  .settings-llm-dialog :deep(.el-form-item) {
    display: block;
    margin-bottom: 18px;
  }
  .settings-llm-dialog :deep(.el-form-item__label) {
    width: auto !important;
    text-align: left;
    padding: 0 0 4px 0;
    line-height: 1.4;
    height: auto;
    float: none;
  }
  .settings-llm-dialog :deep(.el-form-item__content) {
    margin-left: 0 !important;
  }
}
</style>
