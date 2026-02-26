<template>
  <div class="exam-analysis-progress">
    <!-- 展开时覆盖整个 Tab 的报告视图 -->
    <div v-if="reportExpanded" class="report-full-view">
      <div class="report-full-header">
        <span class="report-full-title">分析报告</span>
        <div class="report-full-actions">
          <el-button size="small" :loading="regenerating" @click="regenerateReport">重新生成</el-button>
          <el-button size="small" @click="exportReport">导出 PDF</el-button>
          <el-button size="small" @click="reportExpanded = false">收缩</el-button>
        </div>
      </div>
      <div class="report-full-body" v-if="report">
        <section class="report-section">
          <h5>总体概述</h5>
          <p>{{ report.overview }}</p>
          <p class="report-summary">{{ report.summary }}</p>
        </section>
        <section class="report-section">
          <h5>考频分析</h5>
          <p v-if="report.meta && !report.meta.has_trend" class="report-hint">当前仅包含一年试卷，不进行跨年趋势分析。</p>
          <div class="report-charts-row">
            <div class="chart-wrap">
              <h6>考频占比（饼图）</h6>
              <div ref="chartFrequencyPieRef" class="chart-container"></div>
            </div>
            <div class="chart-wrap">
              <h6>考频出现次数（柱状图）</h6>
              <div ref="chartFrequencyBarRef" class="chart-container"></div>
            </div>
          </div>
          <div class="frequency-tables">
            <div class="frequency-block">
              <h6>总数据</h6>
              <el-table :data="report.frequency_by_point" size="small" max-height="200">
                <el-table-column prop="point_name" label="知识点" />
                <el-table-column prop="count" label="出现次数" width="100" />
                <el-table-column prop="ratio" label="占比" width="80">
                  <template #default="{ row }">{{ (row.ratio * 100).toFixed(1) }}%</template>
                </el-table-column>
              </el-table>
            </div>
            <div v-for="(arr, year) in report.frequency_by_year_and_point" :key="year" class="frequency-block">
              <h6>{{ year }} 年</h6>
              <el-table :data="arr" size="small" max-height="160">
                <el-table-column prop="point_name" label="知识点" />
                <el-table-column prop="count" label="次数" width="80" />
                <el-table-column prop="ratio" label="占比" width="70">
                  <template #default="{ row }">{{ (row.ratio * 100).toFixed(1) }}%</template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </section>
        <section class="report-section">
          <h5>知识点分布</h5>
          <div class="chart-wrap">
            <h6>各知识点覆盖题数（柱状图）</h6>
            <div ref="chartDistributionBarRef" class="chart-container"></div>
          </div>
          <el-table :data="report.distribution_by_point" size="small" max-height="220">
            <el-table-column prop="point_name" label="知识点" />
            <el-table-column prop="question_count" label="覆盖题数" width="90" />
            <el-table-column prop="question_ids" label="题号">
              <template #default="{ row }">{{ (row.question_ids || []).join(', ') }}</template>
            </el-table-column>
          </el-table>
        </section>
        <section class="report-section">
          <h5>考题在各文档的分布情况</h5>
          <div class="chart-wrap">
            <h6>各文档分布占比（饼图）</h6>
            <div ref="chartDocDistPieRef" class="chart-container"></div>
          </div>
          <h6>总表</h6>
          <el-table :data="report.doc_distribution_total || []" size="small" max-height="240">
            <el-table-column prop="question_id" label="题号" width="90" />
            <el-table-column prop="document_title" label="文档" min-width="120" />
            <el-table-column label="页码" width="200">
              <template #default="{ row }">
                <span
                  v-for="(p, i) in (row.page_numbers || [])"
                  :key="i"
                  class="page-link"
                  @click="onJumpToPage(row.document_id, p)"
                >{{ p }}</span>
              </template>
            </el-table-column>
          </el-table>
          <h6 class="doc-dist-sub-title">按年份</h6>
          <el-collapse>
            <el-collapse-item v-for="year in (report.meta?.years || [])" :key="'doc-' + year" :name="'doc-' + year">
              <template #title>{{ year }} 年</template>
              <el-table :data="(report.doc_distribution_by_year || {})[year] || []" size="small" max-height="200">
                <el-table-column prop="question_id" label="题号" width="90" />
                <el-table-column prop="document_title" label="文档" min-width="120" />
                <el-table-column label="页码" width="200">
                  <template #default="{ row }">
                    <span
                      v-for="(p, i) in (row.page_numbers || [])"
                      :key="i"
                      class="page-link"
                      @click="onJumpToPage(row.document_id, p)"
                    >{{ p }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </el-collapse-item>
          </el-collapse>
        </section>
        <section class="report-section">
          <h5>试题—知识点—讲义页码对照表</h5>
          <el-collapse v-model="mappingCollapseYears">
            <el-collapse-item v-for="year in (report.meta?.years || [])" :key="year" :name="year">
              <template #title>{{ year }} 年</template>
              <el-table :data="(report.mapping_table_by_year || {})[year] || []" size="small">
                <el-table-column prop="question_id" label="题号" width="90" />
                <el-table-column prop="point_name" label="知识点" />
                <el-table-column prop="document_title" label="文档" width="120" />
                <el-table-column label="页码" width="180">
                  <template #default="{ row }">
                    <span
                      v-for="(p, i) in (row.page_numbers || [])"
                      :key="i"
                      class="page-link"
                      @click="onJumpToPage(row.document_id, p)"
                    >{{ p }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </el-collapse-item>
          </el-collapse>
        </section>
        <section class="report-section">
          <h5>学习/复习建议</h5>
          <ul class="suggestions-list">
            <li v-for="(s, i) in (report.suggestions || [])" :key="i">{{ s }}</li>
          </ul>
        </section>
      </div>
    </div>

    <!-- 默认：进度 + 报告小卡片 -->
    <template v-else>
      <div class="progress-header">
        <div class="progress-title-row">
          <h4 class="progress-title">习题解析</h4>
          <el-button
            type="primary"
            size="small"
            class="start-analysis-btn"
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
          v-for="lead in topLevelLeads"
          :key="lead.agent_id"
          :item="lead"
          :children="getChildren(lead.agent_id)"
        />
        <p v-if="onlyLeadRunningHint" class="sub-wait-hint">Sub 任务已派发，正在执行中，约 1–2 分钟内有结果，请稍候…</p>
        <p v-if="isPolling" class="sub-wait-hint">分析进行中，进度将自动更新</p>
        <el-empty
          v-if="!topLevelLeads.length"
          description="分析任务未开始或暂无轨迹数据"
          :image-size="100"
          class="empty-trace"
        />
      </div>
      <!-- 仅在所有年份分析结束后且存在报告时显示 -->
      <div v-if="allYearsAnalysisEnded && report" class="report-card">
        <h5 class="report-card-title">分析报告</h5>
        <p class="report-card-desc">{{ report.summary || report.overview }}</p>
        <div class="report-card-actions">
          <el-button type="primary" size="small" @click="openReport">查看报告</el-button>
          <el-button size="small" :loading="regenerating" @click="regenerateReport">重新生成报告</el-button>
        </div>
      </div>
      <!-- 所有年份分析结束但报告拉取失败时显示重试入口 -->
      <div v-else-if="allYearsAnalysisEnded && reportLoadError" class="report-card report-card--retry">
        <p class="report-card-desc">报告未就绪或生成失败</p>
        <el-button size="small" :loading="regenerating" @click="regenerateReport">重新生成报告</el-button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, inject, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import AgentTracePanel from './AgentTracePanel.vue'
import { api, BASE_URL } from '../../../services/api'

const route = useRoute()
const conversationId = computed(() => route.params.conversationId || route.params.id)
const jumpToDocumentPage = inject('jumpToDocumentPage', null)

const agentTraceItems = ref([])
const startAnalysisLoading = ref(false)
const sseSource = ref(null) // 非空时表示正在用 SSE 收流，不轮询
const isPolling = ref(false) // 方案 A：刷新后有 running 时轮询，用于显示提示
let pollTimer = null

const report = ref(null)
const reportExpanded = ref(false)
const reportLoading = ref(false)
const allYearsAnalysisEnded = ref(false) // 仅在此为 true 时显示报告区域
const reportLoadError = ref(false)
const regenerating = ref(false)
const mappingCollapseYears = ref([]) // 默认空 = 全部折叠
const chartFrequencyPieRef = ref(null)
const chartFrequencyBarRef = ref(null)
const chartDistributionBarRef = ref(null)
const chartDocDistPieRef = ref(null)
let chartFrequencyPie = null
let chartFrequencyBar = null
let chartDistributionBar = null
let chartDocDistPie = null
const CHART_TOP_N = 12
// 仅展示 Lead 节点（不含 lead-xxx-done 的重复项），Sub 作为子项展示
const topLevelLeads = computed(() =>
  agentTraceItems.value.filter((i) => i.role === 'lead' && !String(i.agent_id || '').endsWith('-done'))
)
function getChildren(leadAgentId) {
  return agentTraceItems.value.filter((i) => i.role === 'sub' && i.lead_id === leadAgentId)
}
// 仅有单 Lead 且运行中时提示
const onlyLeadRunningHint = computed(() => {
  const leads = topLevelLeads.value
  return leads.length === 1 && leads[0]?.status === 'running'
})

function applyEvent(event) {
  const items = [...agentTraceItems.value]
  switch (event.type) {
    case 'analysis_started':
      agentTraceItems.value = []
      allYearsAnalysisEnded.value = false
      return
    case 'lead_started': {
      const existing = items.findIndex((i) => i.agent_id === event.agent_id)
      const entry = {
        agent_id: event.agent_id,
        role: 'lead',
        label: event.label,
        status: event.status || 'running',
        thinking_blocks: [],
        tool_calls: []
      }
      if (existing !== -1) items[existing] = entry
      else items.push(entry)
      break
    }
    case 'lead_done': {
      const leadId = String(event.agent_id || '').replace(/-done$/, '')
      const indices = items.map((i, idx) => (i.agent_id === leadId ? idx : -1)).filter((i) => i >= 0)
      indices.forEach((idx) => { items[idx] = { ...items[idx], status: 'done' } })
      break
    }
    case 'sub_started':
      items.push({
        agent_id: event.agent_id,
        role: 'sub',
        label: event.label,
        lead_id: event.lead_id,
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
      allYearsAnalysisEnded.value = true
      if (sseSource.value) {
        sseSource.value.close()
        sseSource.value = null
      }
      fetchReport(true)
      return
    default:
      return
  }
  agentTraceItems.value = items
}

// api 成功时返回 response.data，即 { items: [...] }；失败时不覆盖已有列表，避免刷新后误清空 Sub 等记录
async function fetchTrace() {
  if (!conversationId.value || sseSource.value) return
  const res = await api.get(`/api/conversations/${conversationId.value}/exam_analysis/trace`).catch(() => null)
  if (res == null || !Array.isArray(res.items)) return
  let items = res.items
  // 合并 lead-xxx-done 到 lead-xxx，保证树只显示一个 Lead 节点
  const doneIds = new Set()
  items.forEach((i) => {
    if (i.role === 'lead' && String(i.agent_id || '').endsWith('-done')) doneIds.add(i.agent_id)
  })
  items = items.filter((i) => !doneIds.has(i.agent_id))
  doneIds.forEach((aid) => {
    const leadId = String(aid).replace(/-done$/, '')
    items.forEach((it, idx) => {
      if (it.agent_id === leadId) items[idx] = { ...it, status: 'done' }
    })
  })
  // 同一 agent_id 的 Sub 只保留一条：优先保留「内容更多」的（thinking+tool_calls 更长），确保刷新后能显示完整轨迹
  const subByAgentId = new Map()
  const contentSize = (i) => (i.thinking_blocks || []).length + (i.tool_calls || []).length
  items.forEach((i) => {
    if (i.role !== 'sub') return
    const id = i.agent_id
    const existing = subByAgentId.get(id)
    if (!existing || contentSize(i) > contentSize(existing)) subByAgentId.set(id, i)
  })
  items = items.filter((i) => i.role !== 'sub').concat([...subByAgentId.values()])
  // 同一 agent_id 的 lead 只保留一条；Sub 已去重
  const seenLeadIds = new Set()
  agentTraceItems.value = items.filter((i) => {
    if (i.role !== 'lead' || String(i.agent_id || '').endsWith('-done')) return true
    if (seenLeadIds.has(i.agent_id)) return false
    seenLeadIds.add(i.agent_id)
    return true
  })
  const leads = agentTraceItems.value.filter((i) => i.role === 'lead' && !String(i.agent_id || '').endsWith('-done'))
  allYearsAnalysisEnded.value = leads.length > 0 && leads.every((l) => l.status === 'done')
  // 轮询时若已全部完成则停止轮询并拉取报告
  if (pollTimer && allYearsAnalysisEnded.value) {
    clearInterval(pollTimer)
    pollTimer = null
    isPolling.value = false
    fetchReport(true)
  }
}

function startPollIfRunning() {
  if (sseSource.value || pollTimer) return
  const hasRunning = agentTraceItems.value.some((i) => i.status === 'running')
  if (!hasRunning) return
  isPolling.value = true
  pollTimer = setInterval(fetchTrace, 3000)
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
    if (!pollTimer) {
      isPolling.value = true
      pollTimer = setInterval(fetchTrace, 3000)
    }
  }
}

async function fetchReport(openAfterLoad = false) {
  if (!conversationId.value) return
  reportLoading.value = true
  reportLoadError.value = false
  const res = await api.get(`/api/conversations/${conversationId.value}/exam_analysis/report`).catch((e) => {
    if (e?.response?.status === 404) reportLoadError.value = true
    return null
  })
  reportLoading.value = false
  report.value = res || null
  reportLoadError.value = !res
  if (openAfterLoad && res) reportExpanded.value = true
}

function openReport() {
  if (!report.value) return
  reportExpanded.value = true
}

function disposeCharts() {
  if (chartFrequencyPie) {
    chartFrequencyPie.dispose()
    chartFrequencyPie = null
  }
  if (chartFrequencyBar) {
    chartFrequencyBar.dispose()
    chartFrequencyBar = null
  }
  if (chartDistributionBar) {
    chartDistributionBar.dispose()
    chartDistributionBar = null
  }
  if (chartDocDistPie) {
    chartDocDistPie.dispose()
    chartDocDistPie = null
  }
}

function initCharts() {
  const r = report.value
  if (!r) return
  disposeCharts()
  const freq = (r.frequency_by_point || []).slice(0, CHART_TOP_N)
  const dist = (r.distribution_by_point || []).slice(0, CHART_TOP_N)
  if (freq.length && chartFrequencyPieRef.value) {
    chartFrequencyPie = echarts.init(chartFrequencyPieRef.value)
    chartFrequencyPie.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {d}%' },
      legend: {
        orient: 'horizontal',
        bottom: 4,
        left: 'center',
        type: 'scroll',
        width: '95%',
        itemGap: 10,
        itemWidth: 14,
        itemHeight: 10,
        textStyle: { fontSize: 11 },
        pageButtonItemGap: 6,
        pageIconSize: 10,
        pageTextStyle: { fontSize: 10 },
      },
      series: [{
        type: 'pie',
        radius: ['38%', '58%'],
        center: ['50%', '40%'],
        data: freq.map((x) => ({ name: x.point_name, value: Math.round(x.ratio * 10000) / 100 })),
        label: {
          show: true,
          formatter: '{d}%',
          fontSize: 10,
          avoidLabelOverlap: true,
          minMargin: 4,
        },
        labelLine: { length: 8, length2: 4 },
      }],
    })
  }
  if (freq.length && chartFrequencyBarRef.value) {
    chartFrequencyBar = echarts.init(chartFrequencyBarRef.value)
    chartFrequencyBar.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: '12%', right: '8%', top: '8%', bottom: '15%' },
      xAxis: { type: 'category', data: freq.map((x) => x.point_name), axisLabel: { rotate: 35, fontSize: 11 } },
      yAxis: { type: 'value', name: '出现次数' },
      series: [{ type: 'bar', data: freq.map((x) => x.count), itemStyle: { color: '#409eff' } }],
    })
  }
  if (dist.length && chartDistributionBarRef.value) {
    chartDistributionBar = echarts.init(chartDistributionBarRef.value)
    chartDistributionBar.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: '12%', right: '8%', top: '8%', bottom: '15%' },
      xAxis: { type: 'category', data: dist.map((x) => x.point_name), axisLabel: { rotate: 35, fontSize: 11 } },
      yAxis: { type: 'value', name: '覆盖题数' },
      series: [{ type: 'bar', data: dist.map((x) => x.question_count), itemStyle: { color: '#67c23a' } }],
    })
  }
  const docTotal = r.doc_distribution_total || []
  const byDoc = {}
  for (const row of docTotal) {
    const t = row.document_title || '未知文档'
    byDoc[t] = (byDoc[t] || 0) + 1
  }
  const docPieData = Object.entries(byDoc)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, CHART_TOP_N)
  if (docPieData.length && chartDocDistPieRef.value) {
    chartDocDistPie = echarts.init(chartDocDistPieRef.value)
    chartDocDistPie.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c} 条 ({d}%)' },
      legend: {
        orient: 'horizontal',
        bottom: 4,
        left: 'center',
        type: 'scroll',
        width: '95%',
        itemGap: 10,
        itemWidth: 14,
        itemHeight: 10,
        textStyle: { fontSize: 11 },
        pageButtonItemGap: 6,
        pageIconSize: 10,
        pageTextStyle: { fontSize: 10 },
      },
      series: [{
        type: 'pie',
        radius: ['38%', '58%'],
        center: ['50%', '40%'],
        data: docPieData.map((x) => ({ name: x.name, value: x.value })),
        label: {
          show: true,
          formatter: (params) => `${params.percent?.toFixed(1) ?? 0}%`,
          fontSize: 10,
          avoidLabelOverlap: true,
          minMargin: 4,
        },
        labelLine: { length: 8, length2: 4 },
      }],
    })
  }
}

function resizeCharts() {
  chartFrequencyPie?.resize()
  chartFrequencyBar?.resize()
  chartDistributionBar?.resize()
  chartDocDistPie?.resize()
}

watch(
  () => [report.value, reportExpanded.value],
  ([r, expanded]) => {
    if (expanded && r) {
      nextTick(() => initCharts())
    } else {
      disposeCharts()
    }
  },
  { immediate: true }
)

async function regenerateReport() {
  if (!conversationId.value || regenerating.value) return
  regenerating.value = true
  const res = await api
    .post(`/api/conversations/${conversationId.value}/exam_analysis/report/regenerate`)
    .then((r) => ({ ok: true, data: r }))
    .catch((e) => ({ ok: false, detail: e?.response?.data?.detail || e?.message }))
  regenerating.value = false
  if (res.ok) {
    report.value = res.data
    reportLoadError.value = false
    ElMessage.success('报告已重新生成')
  } else {
    ElMessage.warning(res.detail || '重新生成失败')
    fetchReport()
  }
}

function onJumpToPage(documentId, page) {
  if (jumpToDocumentPage && typeof jumpToDocumentPage === 'function') {
    jumpToDocumentPage(documentId, page)
  } else {
    ElMessage.warning('文档未加载或不可用')
  }
}

function exportReport() {
  if (!report.value) return
  ElMessage.info('导出 PDF：暂以 Markdown 下载；PDF 可后续接入')
  const md = [
    '# 试题分析报告',
    '',
    '## 总体概述',
    report.value.overview || '',
    report.value.summary || '',
    '',
    '## 考频分析',
    '（见表格）',
    '',
    '## 学习/复习建议',
    ...(report.value.suggestions || []).map((s) => `- ${s}`),
  ].join('\n')
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `exam-report-${conversationId.value || 'report'}.md`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  window.addEventListener('resize', resizeCharts)
})
// conversationId 就绪或切换时拉取轨迹与报告，immediate 保证刷新后路由就绪即拉取（含 Sub 及历史记录）
watch(conversationId, () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
    isPolling.value = false
  }
  if (!conversationId.value) return
  fetchTrace().then(() => startPollIfRunning())
  fetchReport()
}, { immediate: true })
onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
    isPolling.value = false
  }
  window.removeEventListener('resize', resizeCharts)
  disposeCharts()
})
</script>

<style scoped>
.exam-analysis-progress {
  position: relative;
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
.start-analysis-btn {
  border-radius: 999px;
  padding: 6px 18px;
  font-size: 16px;
  font-weight: 500;
  letter-spacing: 0.02em;
  background-color: var(--el-color-primary-light-5);
  border-color: var(--el-color-primary-light-5);
  color: #ffffff;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.08);
  transition: box-shadow 0.15s ease, transform 0.15s ease, background-color 0.15s ease;
}
.start-analysis-btn:not(:disabled):hover {
  transform: translateY(-0.5px);
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.14);
}
.start-analysis-btn.is-disabled,
.start-analysis-btn:disabled {
  box-shadow: none;
  transform: none;
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
.report-card {
  margin-top: 16px;
  padding: 12px;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  background: var(--bg-card);
}
.report-card-title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.report-card-desc {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--text-tertiary);
  line-height: 1.4;
}
.report-card-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.report-full-view {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  overflow: hidden;
}
.report-full-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
}
.report-full-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}
.report-full-body {
  flex: 1;
  overflow: auto;
  padding: 12px;
}
.report-section {
  margin-bottom: 20px;
}
.report-section h5 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.report-section h6 {
  margin: 8px 0 4px;
  font-size: 13px;
  color: var(--text-secondary);
}
.report-section h6.doc-dist-sub-title {
  margin-top: 14px;
}
.report-summary,
.report-hint {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-top: 4px;
}
.report-charts-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.chart-wrap {
  flex: 1;
  min-width: 280px;
  max-width: 420px;
}
.chart-wrap h6 {
  margin-bottom: 6px;
}
.chart-container {
  width: 100%;
  height: 240px;
  background: var(--el-fill-color-blank);
  border-radius: 6px;
}
.frequency-tables {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.frequency-block {
  margin-bottom: 8px;
}
.page-link {
  margin-right: 6px;
  padding: 2px 6px;
  cursor: pointer;
  color: var(--el-color-primary);
  text-decoration: underline;
}
.page-link:hover {
  opacity: 0.8;
}
.suggestions-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--text-primary);
}
</style>
