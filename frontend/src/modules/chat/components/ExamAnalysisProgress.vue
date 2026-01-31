<template>
  <div class="exam-analysis-progress">
    <div class="progress-header">
      <div class="progress-title-row">
        <h4 class="progress-title">习题解析进度</h4>
        <el-button
          type="primary"
          size="small"
          :loading="startAnalysisLoading"
          :disabled="startAnalysisLoading"
          @click="startAnalysis"
        >
          开始分析
        </el-button>
      </div>
      <p class="progress-desc">多智能体分析任务将在此展示各 Agent 的思考与工具调用</p>
    </div>
    <div class="agent-trace-list">
      <AgentTracePanel
        v-for="item in agentTraceItems"
        :key="item.agent_id"
        :item="item"
      />
      <p v-if="onlyLeadRunningHint" class="sub-wait-hint">Sub 任务已派发，正在执行中，约 1–2 分钟内有结果，请稍候…</p>
      <el-empty
        v-if="!agentTraceItems.length"
        description="分析任务未开始或暂无轨迹数据"
        :image-size="100"
        class="empty-trace"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import AgentTracePanel from './AgentTracePanel.vue'
import { api, BASE_URL } from '../../../services/api'

const route = useRoute()
const conversationId = computed(() => route.params.conversationId || route.params.id)

const agentTraceItems = ref([])
const startAnalysisLoading = ref(false)
const sseSource = ref(null) // 非空时表示正在用 SSE 收流，不轮询
let pollTimer = null
// 仅有 Lead 且运行中时提示：Sub 需约 1–2 分钟才陆续出现
const onlyLeadRunningHint = computed(() => {
  const items = agentTraceItems.value
  if (items.length !== 1) return false
  const one = items[0]
  return one?.role === 'lead' && one?.status === 'running'
})

function applyEvent(event) {
  const items = [...agentTraceItems.value]
  switch (event.type) {
    case 'analysis_started':
      agentTraceItems.value = []
      return
    case 'lead_started':
      items.push({
        agent_id: event.agent_id,
        role: 'lead',
        label: event.label,
        status: event.status || 'running',
        thinking_blocks: [],
        tool_calls: []
      })
      break
    case 'lead_done':
      items.push({
        agent_id: event.agent_id,
        role: 'lead',
        label: event.label || event.agent_id,
        status: 'done',
        thinking_blocks: [],
        tool_calls: []
      })
      break
    case 'sub_started':
      items.push({
        agent_id: event.agent_id,
        role: 'sub',
        label: event.label,
        status: 'running',
        thinking_blocks: [],
        tool_calls: []
      })
      break
    case 'sub_thinking':
      const t = items.find(i => i.agent_id === event.agent_id)
      if (t) {
        t.thinking_blocks = t.thinking_blocks || []
        t.thinking_blocks.push(event.block)
      }
      break
    case 'sub_tool_call':
      const c = items.find(i => i.agent_id === event.agent_id)
      if (c) {
        c.tool_calls = c.tool_calls || []
        c.tool_calls.push(event.call)
      }
      break
    case 'sub_done': {
      const idx = items.findIndex(i => i.agent_id === event.agent_id)
      if (idx !== -1) items[idx] = { ...items[idx], status: 'done' }
      break
    }
    case 'stream_end':
      if (sseSource.value) {
        sseSource.value.close()
        sseSource.value = null
      }
      return
    default:
      return
  }
  agentTraceItems.value = items
}

// api 成功时返回 response.data，即 { items: [...] }，无 res.data 这一层
async function fetchTrace() {
  if (!conversationId.value || sseSource.value) return
  const res = await api.get(`/api/conversations/${conversationId.value}/exam_analysis/trace`).catch(() => ({ items: [] }))
  agentTraceItems.value = res?.items ?? []
}

// 先连 SSE 再 POST start，实时收事件
async function startAnalysis() {
  if (!conversationId.value || startAnalysisLoading.value) return
  startAnalysisLoading.value = true
  const cid = conversationId.value
  const streamUrl = `${BASE_URL}/api/conversations/${cid}/exam_analysis/stream`
  const es = new EventSource(streamUrl)
  sseSource.value = es
  es.onmessage = (e) => {
    const event = JSON.parse(e.data || '{}')
    applyEvent(event)
  }
  es.onerror = () => {
    es.close()
    sseSource.value = null
  }
  const res = await api
    .post(`/api/conversations/${cid}/exam_analysis/start`)
    .then(() => ({ ok: true }))
    .catch((e) => ({ ok: false, detail: e?.response?.data?.detail }))
  startAnalysisLoading.value = false
  if (res.ok) {
    ElMessage.success('分析已启动，实时推送进度')
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = null
  } else {
    ElMessage.warning(res.detail || '启动失败')
    es.close()
    sseSource.value = null
    if (!pollTimer) pollTimer = setInterval(fetchTrace, 3000)
  }
}

onMounted(fetchTrace)
watch(conversationId, () => {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = null
  fetchTrace()
})
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.exam-analysis-progress {
  padding: 12px;
  height: 100%;
  overflow: auto;
}
.progress-header {
  margin-bottom: 16px;
}
.progress-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 4px;
}
.progress-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}
.progress-desc {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 0;
}
.agent-trace-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.empty-trace {
  padding: 24px 0;
}
.sub-wait-hint {
  margin: 12px 0 0;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  border-radius: 6px;
}
</style>
