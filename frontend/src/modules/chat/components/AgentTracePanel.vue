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
        <div v-if="traceEntries.length" class="trace-entries">
          <template v-for="(entry, i) in traceEntries" :key="entry.key">
            <div v-if="entry.type === 'thinking'" class="thinking-block">
              <div class="thinking-title">{{ entry.data.title }}</div>
              <div class="thinking-content">{{ entry.data.content }}</div>
            </div>
            <div v-else class="tool-call-item">
              <div class="tool-call-header" @click.stop="toggleToolExpand(entry.key)">
                <el-icon class="tool-expand-icon" :class="{ expanded: expandedToolKeys.has(entry.key) }">
                  <ArrowRight />
                </el-icon>
                <span class="tool-name">{{ entry.data.name }}</span>
                <el-tag size="small" :type="entry.data.status === 'success' ? 'success' : entry.data.status === 'error' ? 'danger' : 'info'">
                  {{ entry.data.status }}
                </el-tag>
              </div>
              <el-collapse-transition>
                <div v-show="expandedToolKeys.has(entry.key)" v-if="hasResult(entry.data)" class="tool-result-wrap">
                  <div class="tool-result">{{ typeof entry.data.result === 'string' ? entry.data.result : entry.data.result?.message }}</div>
                </div>
              </el-collapse-transition>
            </div>
          </template>
        </div>
        <div v-if="children?.length" class="children-list">
          <AgentTracePanel
            v-for="child in children"
            :key="child.agent_id"
            :item="child"
            :children="[]"
          />
        </div>
      </div>
    </el-collapse-transition>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'
import AgentTracePanel from './AgentTracePanel.vue'

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
  },
  children: {
    type: Array,
    default: () => []
  }
})

const expanded = ref(true)
// 每条工具调用默认折叠，点击展开 result
const expandedToolKeys = ref(new Set())

function toggleToolExpand(key) {
  const next = new Set(expandedToolKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedToolKeys.value = next
}

function hasResult(data) {
  return data?.result != null && (typeof data.result === 'string' ? data.result : data.result?.message) != null
}

const statusText = computed(() => {
  const m = { running: '运行中', done: '完成', failed: '失败' }
  return m[props.item.status] || props.item.status
})

const statusTagType = computed(() => {
  const m = { running: 'warning', done: 'success', failed: 'danger' }
  return m[props.item.status] || 'info'
})

const traceEntries = computed(() => {
  const blocks = props.item.thinking_blocks || []
  const calls = props.item.tool_calls || []
  const hasStep = blocks.some(b => b.step != null) || calls.some(c => c.step != null)
  const entries = []
  blocks.forEach((b, i) => {
    entries.push({ type: 'thinking', step: hasStep ? (b.step ?? i) : i, key: `t-${i}`, data: b })
  })
  calls.forEach((c, i) => {
    entries.push({ type: 'tool_call', step: hasStep ? (c.step ?? 1000 + i) : 1000 + i, key: `c-${c.id || i}`, data: c })
  })
  entries.sort((a, b) => a.step - b.step)
  return entries
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
.trace-entries {
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
.tool-call-item {
  font-size: 13px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border-subtle);
}
.tool-call-item:last-child {
  border-bottom: none;
}
.tool-call-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}
.tool-call-header:hover {
  color: var(--text-secondary);
}
.tool-expand-icon {
  transition: transform 0.2s;
  flex-shrink: 0;
}
.tool-expand-icon.expanded {
  transform: rotate(90deg);
}
.tool-name {
  font-weight: 500;
  color: var(--text-primary);
}
.tool-result-wrap {
  padding-left: 20px;
  margin-top: 4px;
}
.tool-result {
  font-size: 12px;
  color: var(--text-tertiary);
  white-space: pre-wrap;
  word-break: break-word;
}
.children-list {
  margin-top: 12px;
  padding-left: 12px;
  border-left: 2px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
