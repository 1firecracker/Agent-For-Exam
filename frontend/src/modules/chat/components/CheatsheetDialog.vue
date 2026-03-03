<template>
  <el-dialog
    v-model="visible"
    title="生成 Cheatsheet"
    width="90%"
    top="3vh"
    :before-close="handleClose"
    class="cheatsheet-dialog"
    :close-on-click-modal="false"
  >
    <div class="cheatsheet-body">
      <!-- 左侧设置面板 -->
      <div class="settings-panel">
        <h4 class="panel-title">页面设置</h4>
        <div class="setting-item">
          <label>纸张类型</label>
          <el-select v-model="pageSize" size="small">
            <el-option label="A4" value="A4" />
            <el-option label="A3" value="A3" />
            <el-option label="Letter" value="Letter" />
          </el-select>
        </div>
        <div class="setting-item">
          <label>边距 (mm)</label>
          <el-slider v-model="marginMm" :min="5" :max="30" :step="1" show-input size="small" />
        </div>
        <div class="setting-item">
          <label>字号 (px)</label>
          <el-slider v-model="fontSizePx" :min="7" :max="16" :step="1" show-input size="small" />
        </div>
        <div class="setting-item">
          <label>分栏</label>
          <el-radio-group v-model="columns" size="small">
            <el-radio-button :value="1">1</el-radio-button>
            <el-radio-button :value="2">2</el-radio-button>
            <el-radio-button :value="3">3</el-radio-button>
          </el-radio-group>
        </div>
        <div class="setting-item">
          <label>载入文档图片</label>
          <el-switch v-model="includeImages" />
        </div>

        <div class="setting-item">
          <label>自定义提示词</label>
          <el-input
            v-model="customPrompt"
            type="textarea"
            :rows="3"
            placeholder="例如：重点关注公式和定义；只总结第3章；用英文输出..."
            resize="vertical"
            size="small"
          />
        </div>

        <el-divider />

        <!-- 文档选择区 -->
        <div class="setting-item">
          <label>选择文档</label>
          <div v-if="docList.length === 0" class="doc-empty">暂无已完成的文档</div>
          <el-checkbox-group v-else v-model="selectedFileIds" class="doc-check-list">
            <el-checkbox v-for="d in docList" :key="d.file_id" :value="d.file_id" :label="d.file_id" class="doc-check-item">
              <span class="doc-name" :title="d.filename">{{ d.filename }}</span>
            </el-checkbox>
          </el-checkbox-group>
        </div>

        <el-button type="primary" :loading="generating"
          :disabled="generating || selectedFileIds.length === 0"
          style="width:100%;border-radius:8px" @click="handleGenerate">
          {{ generating ? '生成中...' : `生成 Cheatsheet (${selectedFileIds.length})` }}
        </el-button>
        <div v-if="progressMsg && generating" class="progress-msg">{{ progressMsg }}</div>
        <el-button style="width:100%;margin-top:8px;margin-left:0;border-radius:8px" @click="handleExportPDF">
          导出 PDF
        </el-button>
        <el-divider />
        <div class="setting-item">
          <el-switch v-model="editMode" active-text="编辑模式" />
        </div>
        <div v-if="pageHtmls.length > 1" class="page-indicator">共 {{ pageHtmls.length }} 页</div>
      </div>

      <!-- 右侧预览/编辑区 -->
      <div class="preview-panel">
        <div v-if="editMode" class="edit-area">
          <textarea v-model="markdownContent" class="markdown-editor"
            placeholder="在此编辑 Markdown 内容..."></textarea>
        </div>

        <div v-else class="paper-wrapper">
          <!-- 隐藏测量容器：单列渲染，用于获取每个元素的真实高度 -->
          <div ref="measureRef" class="measure-box" :style="measureStyle" v-html="renderedHtml"></div>

          <!-- 分页预览：每页独立容器，column-fill: auto -->
          <div class="pages-stack">
            <div v-for="(html, idx) in pageHtmls" :key="idx"
              class="page-sheet" :style="pageSheetStyle">
              <div class="page-num">{{ idx + 1 }} / {{ pageHtmls.length }}</div>
              <div class="page-content" :style="pageContentStyle" v-html="html"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { marked } from 'marked'
import { BASE_URL } from '../../../services/api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  subjectId: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const visible = ref(false)
watch(() => props.modelValue, v => { visible.value = v })
watch(visible, v => {
  emit('update:modelValue', v)
  if (v) loadDocList()
})

const pageSize = ref('A4')
const marginMm = ref(10)
const fontSizePx = ref(9)
const columns = ref(2)
const includeImages = ref(false)
const editMode = ref(false)
const generating = ref(false)
const imageRefs = ref([])
const customPrompt = ref('')
const progressMsg = ref('')
const measureRef = ref(null)
const pageHtmls = ref([])
const docList = ref([])
const selectedFileIds = ref([])

const MM_TO_PX = 96 / 25.4

async function loadDocList() {
  if (!props.subjectId) return
  try {
    const resp = await fetch(`${BASE_URL}/api/subjects/${props.subjectId}/documents`)
    const data = await resp.json()
    const docs = (data.documents || []).filter(d => d.status === 'completed')
    docList.value = docs
    selectedFileIds.value = docs.map(d => d.file_id)
  } catch { docList.value = []; selectedFileIds.value = [] }
}

function buildPlaceholder() {
  const langs = [
    { title: '中文', line: '示例文字。这是一段用于预览排版效果的占位内容，请上传文档后点击生成。' },
    { title: 'English', line: 'Sample text. This is placeholder content for previewing the layout. Upload documents and click Generate.' },
    { title: 'Français', line: "Texte d'exemple. Ceci est un contenu de substitution pour prévisualiser la mise en page." },
    { title: 'Русский', line: 'Пример текста. Это содержимое-заполнитель для предварительного просмотра макета.' },
  ]
  let md = '# Cheatsheet Preview\n\n'
  for (const { title, line } of langs) {
    md += `## ${title}\n\n`
    for (let i = 0; i < 50; i++) md += `- ${line}\n`
    md += '\n'
  }
  return md
}

const markdownContent = ref(buildPlaceholder())

const PAGE_DIMS = { A4: { w: 210, h: 297 }, A3: { w: 297, h: 420 }, Letter: { w: 216, h: 279 } }
const contentWidthMm = computed(() => PAGE_DIMS[pageSize.value].w - 2 * marginMm.value)
const contentHeightMm = computed(() => PAGE_DIMS[pageSize.value].h - 2 * marginMm.value)

// 每页可容纳的单列内容高度 = 内容区高度 × 列数
const pageCapacityPx = computed(() => contentHeightMm.value * MM_TO_PX * columns.value)

const CONTENT_CSS = `
  h1 { font-size:1.3em; margin:0.3em 0 0.2em; }
  h2 { font-size:1.15em; margin:0.4em 0 0.2em; border-bottom:1px solid #ccc; padding-bottom:2px; }
  h3 { font-size:1.05em; margin:0.3em 0 0.15em; }
  ul,ol { margin:0.15em 0; padding-left:1.3em; }
  li { margin:0.05em 0; }
  p { margin:0.15em 0; }
  code { background:#f0f0f0; padding:1px 3px; border-radius:2px; font-size:0.9em; }
  pre { background:#f6f6f6; padding:6px; border-radius:4px; overflow-x:auto; font-size:0.85em; }
  blockquote { border-left:3px solid #ddd; margin:0.3em 0; padding-left:8px; color:#666; }
  .cs-page-img { max-width:100%; height:auto; margin:4px 0; border:1px solid #ddd; border-radius:4px; }
`

// 测量容器：单列渲染，获取真实内容高度
const measureStyle = computed(() => ({
  position: 'absolute', visibility: 'hidden', pointerEvents: 'none', zIndex: -1,
  width: `${contentWidthMm.value}mm`,
  fontSize: `${fontSizePx.value}px`,
  lineHeight: '1.35',
  fontFamily: "'Inter','PingFang SC','Microsoft YaHei',sans-serif",
  columnCount: 1,
}))

const pageSheetStyle = computed(() => {
  const dim = PAGE_DIMS[pageSize.value]
  return {
    width: `${dim.w}mm`, height: `${dim.h}mm`,
    padding: `${marginMm.value}mm`, boxSizing: 'border-box', position: 'relative',
  }
})

const pageContentStyle = computed(() => ({
  width: '100%',
  height: `${contentHeightMm.value}mm`,
  overflow: 'hidden',
  columnCount: columns.value,
  columnFill: 'auto',
  columnGap: '12px',
  fontSize: `${fontSizePx.value}px`,
  lineHeight: '1.35',
  fontFamily: "'Inter','PingFang SC','Microsoft YaHei',sans-serif",
  color: '#222',
}))

const renderedHtml = computed(() => {
  if (!markdownContent.value) return ''
  // Strip ```markdown ... ``` code fences that LLM sometimes wraps output in
  let md = markdownContent.value
    .replace(/^```(?:markdown|md)?\s*\n?/i, '')
    .replace(/\n?```\s*$/, '')
  let html = marked.parse(md)
  if (includeImages.value && imageRefs.value.length > 0) {
    html = html.replace(/<!-- PAGE:([^:]+):(\d+) -->/g, (_, fid, pg) =>
      `<img src="${BASE_URL}/api/subjects/${props.subjectId}/documents/${fid}/slides/${pg}/image" class="cs-page-img" />`)
  }
  return html
})

// 将渲染后的 HTML 按内容高度拆分成独立的页面块
function buildPageHtml(items) {
  let html = ''
  let openTag = null
  for (const it of items) {
    if (it.listTag) {
      if (openTag !== it.listTag) {
        if (openTag) html += `</${openTag}>`
        html += `<${it.listTag}>`
        openTag = it.listTag
      }
      html += it.html
    } else {
      if (openTag) { html += `</${openTag}>`; openTag = null }
      html += it.html
    }
  }
  if (openTag) html += `</${openTag}>`
  return html
}

function recalcPages() {
  nextTick(() => {
    const el = measureRef.value
    if (!el || !el.children.length) {
      pageHtmls.value = [renderedHtml.value]
      return
    }

    const cap = pageCapacityPx.value

    // 将顶层元素展平：长列表拆成单个 li
    const items = []
    for (const child of el.children) {
      const tag = child.tagName.toLowerCase()
      if ((tag === 'ul' || tag === 'ol') && child.children.length > 1) {
        for (const li of child.children) {
          items.push({ html: li.outerHTML, height: li.getBoundingClientRect().height, listTag: tag })
        }
      } else {
        items.push({ html: child.outerHTML, height: child.getBoundingClientRect().height, listTag: null })
      }
    }

    const groups = []
    let cur = []
    let acc = 0
    for (const it of items) {
      if (acc + it.height > cap && cur.length > 0) {
        groups.push(buildPageHtml(cur))
        cur = []; acc = 0
      }
      cur.push(it)
      acc += it.height
    }
    if (cur.length > 0) groups.push(buildPageHtml(cur))

    pageHtmls.value = groups.length > 0 ? groups : [renderedHtml.value]
  })
}

watch([renderedHtml, pageSize, marginMm, fontSizePx, columns], recalcPages, { immediate: true })
watch(visible, v => { if (v) recalcPages() })

async function handleGenerate() {
  if (!props.subjectId) return
  generating.value = true; imageRefs.value = []; editMode.value = false; progressMsg.value = ''
  let llmContent = ''
  try {
    const resp = await fetch(`${BASE_URL}/api/subjects/${props.subjectId}/cheatsheet/generate`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        include_images: includeImages.value,
        file_ids: selectedFileIds.value,
        custom_prompt: customPrompt.value || null,
      }),
    })
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = '', hasReal = false
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n'); buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const d = JSON.parse(line)
          if (d.content) {
            if (!hasReal) { markdownContent.value = ''; hasReal = true }
            llmContent += d.content; markdownContent.value = llmContent
          } else if (d.image_refs) { imageRefs.value = d.image_refs
          } else if (d.progress) { progressMsg.value = d.progress }
        } catch {}
      }
    }
    if (buffer.trim()) { try { const d = JSON.parse(buffer); if (d.content) markdownContent.value = (llmContent||'') + d.content } catch {} }
  } catch {} finally { generating.value = false }
}

function handleExportPDF() {
  const w = window.open('', '_blank'); if (!w) return
  const dim = PAGE_DIMS[pageSize.value]
  const cH = contentHeightMm.value
  const pagesMarkup = pageHtmls.value.map(html =>
    `<div class="page-box">${html}</div>`
  ).join('\n')
  w.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>Cheatsheet</title>
<style>
  @page { size:${dim.w}mm ${dim.h}mm; margin:${marginMm.value}mm; }
  body { margin:0; padding:0; font-family:'Inter','PingFang SC','Microsoft YaHei',sans-serif;
    font-size:${fontSizePx.value}px; line-height:1.35; color:#222; }
  .page-box {
    column-count:${columns.value}; column-fill:auto; column-gap:12px;
    height:${cH}mm; overflow:hidden; box-sizing:border-box;
    break-after:page;
  }
  .page-box:last-child { break-after:auto; }
  ${CONTENT_CSS}
</style></head><body>${pagesMarkup}</body></html>`)
  w.document.close(); w.onload = () => { w.print() }
}

function handleClose() { visible.value = false }
</script>

<style scoped>
.cheatsheet-dialog :deep(.el-dialog__body) { padding:0; height:calc(90vh - 100px); overflow:hidden; }
.cheatsheet-body { display:flex; height:100%; }
.settings-panel { width:260px; flex-shrink:0; padding:20px; border-right:1px solid var(--border-subtle); overflow-y:auto; background:var(--bg-sidebar); }
.panel-title { margin:0 0 16px; font-size:15px; font-weight:600; }
.setting-item { margin-bottom:16px; }
.setting-item > label { display:block; font-size:13px; color:var(--text-secondary); margin-bottom:6px; }
.setting-item :deep(.el-select) { width:100%; }
.page-indicator { text-align:center; font-size:12px; color:var(--text-tertiary); margin-top:8px; }
.progress-msg { font-size:11px; color:var(--color-accent); text-align:center; margin-top:6px; }
.doc-empty { font-size:12px; color:var(--text-tertiary); padding:8px 0; }
.doc-check-list { display:flex; flex-direction:column; gap:4px; max-height:150px; overflow-y:auto; }
.doc-check-item { margin-right:0 !important; }
.doc-check-item :deep(.el-checkbox__label) { font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:180px; }
.doc-name { font-size:12px; }

.preview-panel { flex:1; overflow:auto; background:#e8e8e8; display:flex; justify-content:center; padding:24px; position:relative; }
.edit-area { width:100%; }
.markdown-editor { width:100%; height:100%; min-height:500px; border:none; resize:none; font-family:'Courier New',monospace; font-size:13px; line-height:1.5; padding:20px; background:white; border-radius:4px; outline:none; color:var(--text-primary); }

.paper-wrapper { display:flex; flex-direction:column; align-items:center; width:100%; }
.measure-box { position:absolute; visibility:hidden; pointer-events:none; z-index:-1; }
.pages-stack { display:flex; flex-direction:column; align-items:center; gap:24px; }
.page-sheet { background:white; box-shadow:0 2px 12px rgba(0,0,0,0.15); border-radius:2px; flex-shrink:0; }
.page-num { position:absolute; bottom:4px; right:8px; font-size:10px; color:#bbb; }
.page-content { overflow:hidden; }

/* 内容样式：同时作用于测量容器和页面内容 */
.measure-box :deep(h1), .page-content :deep(h1) { font-size:1.3em; margin:0.3em 0 0.2em; }
.measure-box :deep(h2), .page-content :deep(h2) { font-size:1.15em; margin:0.4em 0 0.2em; border-bottom:1px solid #ccc; padding-bottom:2px; }
.measure-box :deep(h3), .page-content :deep(h3) { font-size:1.05em; margin:0.3em 0 0.15em; }
.measure-box :deep(ul), .page-content :deep(ul),
.measure-box :deep(ol), .page-content :deep(ol) { margin:0.15em 0; padding-left:1.3em; }
.measure-box :deep(li), .page-content :deep(li) { margin:0.05em 0; }
.measure-box :deep(p), .page-content :deep(p) { margin:0.15em 0; }
.measure-box :deep(code), .page-content :deep(code) { background:#f0f0f0; padding:1px 3px; border-radius:2px; font-size:0.9em; }
.measure-box :deep(pre), .page-content :deep(pre) { background:#f6f6f6; padding:6px; border-radius:4px; overflow-x:auto; font-size:0.85em; }
.measure-box :deep(blockquote), .page-content :deep(blockquote) { border-left:3px solid #ddd; margin:0.3em 0; padding-left:8px; color:#666; }
.measure-box :deep(.cs-page-img), .page-content :deep(.cs-page-img) { max-width:100%; height:auto; margin:4px 0; border:1px solid #ddd; border-radius:4px; }
</style>
