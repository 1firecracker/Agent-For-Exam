<template>
  <div class="agent-trace-panel">
    <div class="panel-header" @click="expanded = !expanded">
      <div class="header-left">
        <el-icon class="expand-icon" :class="{ expanded }">
          <ArrowRight />
        </el-icon>
        <span class="agent-label">{{ item.label }}</span>
        <el-tag size="small" :type="statusTagType" class="status-tag">
          {{ statusText }}
        </el-tag>
      </div>
      <span v-if="item.tool_calls?.length" class="tool-count">
        {{ item.tool_calls.length }} 次调用
      </span>
    </div>
    <el-collapse-transition>
      <div v-show="expanded" class="panel-body">
        <div v-if="item.thinking_blocks?.length" class="thinking-blocks">
          <div
            v-for="(block, i) in item.thinking_blocks"
            :key="i"
            class="thinking-block"
          >
            <div class="thinking-title">{{ block.title }}</div>
            <div class="thinking-content">{{ block.content }}</div>
          </div>
        </div>
        <div v-if="item.tool_calls?.length" class="tool-calls">
          <div class="tool-calls-title">工具调用</div>
          <div
            v-for="tc in item.tool_calls"
            :key="tc.id"
            class="tool-call-item"
          >
            <span class="tool-name">{{ tc.name }}</span>
            <el-tag size="small" :type="tc.status === 'success' ? 'success' : tc.status === 'error' ? 'danger' : 'info'">
              {{ tc.status }}
            </el-tag>
            <div v-if="tc.result?.message" class="tool-result">{{ tc.result.message }}</div>
          </div>
        </div>
      </div>
    </el-collapse-transition>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'

const props = defineProps({
  item: {
    type: Object,
    required: true,
    default: () => ({
      agent_id: '',
      label: '',
      status: 'done',
      thinking_blocks: [],
      tool_calls: []
    })
  }
})

const expanded = ref(true)

const statusText = computed(() => {
  const m = { running: '运行中', done: '完成', failed: '失败' }
  return m[props.item.status] || props.item.status
})

const statusTagType = computed(() => {
  const m = { running: 'warning', done: 'success', failed: 'danger' }
  return m[props.item.status] || 'info'
})
</script>

<style scoped>
.agent-trace-panel {
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-card);
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  cursor: pointer;
  user-select: none;
}
.panel-header:hover {
  background: var(--bg-hover);
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.expand-icon {
  transition: transform 0.2s;
}
.expand-icon.expanded {
  transform: rotate(90deg);
}
.agent-label {
  font-weight: 500;
  color: var(--text-primary);
}
.status-tag {
  margin-left: 4px;
}
.tool-count {
  font-size: 12px;
  color: var(--text-tertiary);
}
.panel-body {
  padding: 0 12px 12px;
  border-top: 1px solid var(--border-subtle);
}
.thinking-blocks {
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.thinking-block {
  font-size: 13px;
}
.thinking-title {
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
.thinking-content {
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}
.tool-calls {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-subtle);
}
.tool-calls-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--text-secondary);
}
.tool-call-item {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border-subtle);
}
.tool-call-item:last-child {
  border-bottom: none;
}
.tool-name {
  font-weight: 500;
  color: var(--text-primary);
}
.tool-result {
  width: 100%;
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 4px;
}
</style>
