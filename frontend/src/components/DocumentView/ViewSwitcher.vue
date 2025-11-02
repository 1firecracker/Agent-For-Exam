<template>
  <div class="view-switcher">
    <!-- 视图切换按钮 -->
    <div class="switcher-header">
      <el-button-group>
        <el-button
          :type="viewMode === 'ppt' ? 'primary' : 'default'"
          :icon="Document"
          @click="viewMode = 'ppt'"
        >
          PPT 视图
        </el-button>
        <el-button
          :type="viewMode === 'graph' ? 'primary' : 'default'"
          :icon="Connection"
          @click="viewMode = 'graph'"
        >
          知识图谱
        </el-button>
      </el-button-group>
    </div>
    
    <!-- 视图内容 -->
    <div class="view-content">
      <!-- PPT 视图 -->
      <div v-if="viewMode === 'ppt'" class="ppt-view">
        <PPTViewer 
          v-if="convStore.currentConversationId" 
          :default-file-id="currentDocumentId"
        />
        <el-empty
          v-else
          description="请先选择或创建一个对话"
          :image-size="120"
        />
      </div>
      
      <!-- 知识图谱视图 -->
      <div v-else class="graph-view">
        <GraphViewer v-if="convStore.currentConversationId" />
        <el-empty
          v-else
          description="请先选择或创建一个对话"
          :image-size="120"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Document, Connection } from '@element-plus/icons-vue'
import { useConversationStore } from '../../stores/conversationStore'
import PPTViewer from '../PPTViewer/PPTViewer.vue'
import GraphViewer from '../GraphViewer/GraphViewer.vue'

const emit = defineEmits(['view-mode-change'])

const props = defineProps({
  currentDocumentId: {
    type: String,
    default: null
  }
})

const convStore = useConversationStore()
const viewMode = ref('ppt') // 'ppt' 或 'graph'

// 通知父组件视图模式变化
watch(viewMode, (newMode) => {
  emit('view-mode-change', newMode)
})

// 当文档变化时，如果当前是PPT视图，自动加载
watch(() => props.currentDocumentId, (newDocId) => {
  if (newDocId && viewMode.value === 'ppt') {
    // PPTViewer会自动响应defaultFileId变化
  }
})
</script>

<style scoped>
.view-switcher {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.switcher-header {
  padding: 12px;
  border-bottom: 1px solid #e4e7ed;
  background-color: #fff;
  display: flex;
  justify-content: center;
}

.view-content {
  flex: 1;
  overflow: hidden;
  position: relative;
}

.ppt-view,
.graph-view {
  width: 100%;
  height: 100%;
  overflow: hidden;
}
</style>

