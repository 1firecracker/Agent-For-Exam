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
        <el-button
          :type="viewMode === 'exercise' ? 'primary' : 'default'"
          :icon="EditPen"
          @click="viewMode = 'exercise'"
        >
          Agent试题模拟
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
      <div v-else-if="viewMode === 'graph'" class="graph-view">
        <GraphViewer v-if="convStore.currentConversationId" />
        <el-empty
          v-else
          description="请先选择或创建一个对话"
          :image-size="120"
        />
      </div>
      
      <!-- Agent试题模拟视图 -->
      <div v-else-if="viewMode === 'exercise'" class="exercise-view">
        <ExerciseViewer v-if="convStore.currentConversationId" />
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
import { Document, Connection, EditPen } from '@element-plus/icons-vue'
import { useConversationStore } from '../../stores/conversationStore'
import PPTViewer from '../PPTViewer/PPTViewer.vue'
import GraphViewer from '../GraphViewer/GraphViewer.vue'
import ExerciseViewer from '../ExerciseViewer/ExerciseViewer.vue'

const emit = defineEmits(['view-mode-change'])

const props = defineProps({
  currentDocumentId: {
    type: String,
    default: null
  }
})

const convStore = useConversationStore()
const viewMode = ref('ppt') // 'ppt'、'graph' 或 'exercise'

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
.graph-view,
.exercise-view {
  width: 100%;
  height: 100%;
  overflow: hidden;
}
</style>

