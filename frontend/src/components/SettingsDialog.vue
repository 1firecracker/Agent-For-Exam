<template>
  <el-dialog
    v-model="dialogVisible"
    title="LLM 配置设置"
    width="800px"
    :before-close="handleClose"
  >
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

// 计算属性
const configs = computed(() => settingsStore.configs)
const modelLists = computed(() => settingsStore.modelLists)

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

