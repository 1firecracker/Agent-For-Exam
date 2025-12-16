<template>
  <el-dialog
    v-model="dialogVisible"
    title="LLM 配置设置"
    width="800px"
    :before-close="handleClose"
  >
    <el-tabs v-model="activeTab">
      <el-tab-pane label="知识图谱抽取" name="knowledge_graph">
        <ConfigForm 
          :config="configs.knowledge_graph"
          :model-lists="modelLists"
          @update="handleUpdate('knowledge_graph', $event)"
        />
      </el-tab-pane>
      
      <el-tab-pane label="聊天对话" name="chat">
        <ConfigForm 
          :config="configs.chat"
          :model-lists="modelLists"
          @update="handleUpdate('chat', $event)"
        />
      </el-tab-pane>
      
      <el-tab-pane label="思维导图生成" name="mindmap">
        <ConfigForm 
          :config="configs.mindmap"
          :model-lists="modelLists"
          @update="handleUpdate('mindmap', $event)"
        />
      </el-tab-pane>
      
      <el-tab-pane label="嵌入向量" name="embedding">
        <ConfigForm 
          :config="configs.embedding"
          :model-lists="modelLists"
          default-binding="siliconflow"
          @update="handleUpdate('embedding', $event)"
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
import { useSettingsStore } from '../store/settingsStore'
import ConfigForm from './ConfigForm.vue'

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

const configs = computed(() => settingsStore.configs)
const modelLists = computed(() => settingsStore.modelLists)

watch(() => props.modelValue, (val) => {
  dialogVisible.value = val
  if (val) {
    loadConfig()
  }
})

watch(dialogVisible, (val) => {
  emit('update:modelValue', val)
})

async function loadConfig() {
  try {
    await settingsStore.loadConfig()
  } catch (error) {
    ElMessage.error('加载配置失败: ' + (error.response?.data?.detail || error.message))
  }
}

async function handleUpdate(scene, config) {
  try {
    await settingsStore.updateConfig(scene, config)
    ElMessage.success('配置已更新并立即生效')
  } catch (error) {
    ElMessage.error('更新配置失败: ' + (error.response?.data?.detail || error.message))
  }
}

function handleClose() {
  dialogVisible.value = false
}

onMounted(() => {
  if (props.modelValue) {
    loadConfig()
  }
})
</script>


