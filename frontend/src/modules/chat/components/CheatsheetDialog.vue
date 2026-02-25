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

        <el-divider />

        <el-button
          type="primary"
          :loading="generating"
          :disabled="generating"
          style="width: 100%; border-radius: 8px;"
          @click="handleGenerate"
        >
          {{ generating ? '生成中...' : '生成 Cheatsheet' }}
        </el-button>

        <el-button
          style="width: 100%; margin-top: 8px; margin-left: 0; border-radius: 8px;"
          @click="handleExportPDF"
        >
          导出 PDF
        </el-button>

        <el-divider />

        <div class="setting-item">
          <el-switch v-model="editMode" active-text="编辑模式" />
        </div>

        <div v-if="totalPages > 1" class="page-indicator">
          共 {{ totalPages }} 页
        </div>
      </div>

      <!-- 右侧预览/编辑区 -->
      <div class="preview-panel">
        <!-- 编辑模式 -->
        <div v-if="editMode" class="edit-area">
          <textarea
            v-model="markdownContent"
            class="markdown-editor"
            placeholder="在此编辑 Markdown 内容..."
          ></textarea>
        </div>

        <!-- 预览模式：分页显示 -->
        <div v-else class="paper-wrapper">
          <!-- 隐藏的测量容器：与打印内容区域完全相同的 CSS，高度自动 -->
          <div
            ref="measureRef"
            class="measure-box"
            :style="measureStyle"
            v-html="renderedHtml"
          ></div>

          <!-- 分页预览 -->
          <div class="pages-stack">
            <div
              v-for="n in totalPages"
              :key="n"
              class="page-sheet"
              :style="pageSheetStyle"
            >
              <div class="page-num">{{ n }} / {{ totalPages }}</div>
              <div class="page-clip" :style="pageClipStyle">
                <div
                  class="page-slice"
                  :style="{ ...contentCssVars, transform: `translateY(-${(n - 1) * clipHeightPx}px)` }"
                  v-html="renderedHtml"
                ></div>
              </div>
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
watch(visible, v => emit('update:modelValue', v))

const pageSize = ref('A4')
const marginMm = ref(10)
const fontSizePx = ref(9)
const columns = ref(2)
const includeImages = ref(false)
const editMode = ref(false)
const generating = ref(false)
const imageRefs = ref([])
const measureRef = ref(null)
const totalPages = ref(1)

const MM_TO_PX = 96 / 25.4

function buildPlaceholder() {
  const langs = [
    { title: '中文', line: '示例文字。这是一段用于预览排版效果的占位内容，请上传文档后点击生成。' },
    { title: 'English', line: 'Sample text. This is placeholder content for previewing the layout. Upload documents and click Generate.' },
    { title: 'Français', line: 'Texte d\'exemple. Ceci est un contenu de substitution pour prévisualiser la mise en page.' },
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

const PAGE_DIMS = {
  A4: { w: 210, h: 297 },
  A3: { w: 297, h: 420 },
  Letter: { w: 216, h: 279 },
}

const contentWidthMm = computed(() => PAGE_DIMS[pageSize.value].w - 2 * marginMm.value)
const contentHeightMm = computed(() => PAGE_DIMS[pageSize.value].h - 2 * marginMm.value)
const clipHeightPx = computed(() => contentHeightMm.value * MM_TO_PX)

// 共用内容 CSS（用于测量容器 + 页面切片 + 打印输出）
const CONTENT_CSS = `
  h1 { font-size: 1.3em; margin: 0.3em 0 0.2em; }
  h2 { font-size: 1.15em; margin: 0.4em 0 0.2em; border-bottom: 1px solid #ccc; padding-bottom: 2px; }
  h3 { font-size: 1.05em; margin: 0.3em 0 0.15em; }
  ul, ol { margin: 0.15em 0; padding-left: 1.3em; }
  li { margin: 0.05em 0; }
  p { margin: 0.15em 0; }
  code { background: #f0f0f0; padding: 1px 3px; border-radius: 2px; font-size: 0.9em; }
  pre { background: #f6f6f6; padding: 6px; border-radius: 4px; overflow-x: auto; font-size: 0.85em; }
  blockquote { border-left: 3px solid #ddd; margin: 0.3em 0; padding-left: 8px; color: #666; }
  .cs-page-img { max-width: 100%; height: auto; margin: 4px 0; border: 1px solid #ddd; border-radius: 4px; }
`

// 测量容器样式：宽度 = 内容区宽度，高度自动，应用分栏和字号
const measureStyle = computed(() => ({
  position: 'absolute',
  visibility: 'hidden',
  pointerEvents: 'none',
  width: `${contentWidthMm.value}mm`,
  fontSize: `${fontSizePx.value}px`,
  lineHeight: '1.35',
  fontFamily: "'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif",
  columnCount: columns.value,
  columnGap: '12px',
}))

// 每页外框样式：纸张完整尺寸
const pageSheetStyle = computed(() => {
  const dim = PAGE_DIMS[pageSize.value]
  return {
    width: `${dim.w}mm`,
    height: `${dim.h}mm`,
    padding: `${marginMm.value}mm`,
    boxSizing: 'border-box',
    position: 'relative',
  }
})

// 裁剪区样式：内容区域的固定高度
const pageClipStyle = computed(() => ({
  width: '100%',
  height: `${contentHeightMm.value}mm`,
  overflow: 'hidden',
}))

// 每个切片的内容样式
const contentCssVars = computed(() => ({
  width: `${contentWidthMm.value}mm`,
  fontSize: `${fontSizePx.value}px`,
  lineHeight: '1.35',
  fontFamily: "'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif",
  columnCount: columns.value,
  columnGap: '12px',
  color: '#222',
}))

const renderedHtml = computed(() => {
  if (!markdownContent.value) return ''
  let html = marked.parse(markdownContent.value)
  if (includeImages.value && imageRefs.value.length > 0) {
    html = html.replace(/<!-- PAGE:([^:]+):(\d+) -->/g, (_, fileId, page) => {
      return `<img src="${BASE_URL}/api/subjects/${props.subjectId}/documents/${fileId}/slides/${page}/image" class="cs-page-img" />`
    })
  }
  return html
})

// 测量内容高度并计算总页数
function recalcPages() {
  nextTick(() => {
    if (!measureRef.value) return
    const h = measureRef.value.scrollHeight
    totalPages.value = Math.max(1, Math.ceil(h / clipHeightPx.value))
  })
}

watch([renderedHtml, pageSize, marginMm, fontSizePx, columns], recalcPages, { immediate: true })
watch(visible, v => { if (v) recalcPages() })

async function handleGenerate() {
  if (!props.subjectId) return
  generating.value = true
  imageRefs.value = []
  editMode.value = false
  let llmContent = ''

  try {
    const resp = await fetch(`${BASE_URL}/api/subjects/${props.subjectId}/cheatsheet/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ include_images: includeImages.value }),
    })
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let hasRealContent = false

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const data = JSON.parse(line)
          if (data.content) {
            if (!hasRealContent) { markdownContent.value = ''; hasRealContent = true }
            llmContent += data.content
            markdownContent.value = llmContent
          } else if (data.image_refs) {
            imageRefs.value = data.image_refs
          }
        } catch { /* ignore */ }
      }
    }
    if (buffer.trim()) {
      try {
        const data = JSON.parse(buffer)
        if (data.content) { markdownContent.value = (llmContent || '') + data.content }
      } catch { /* ignore */ }
    }
  } catch { /* keep placeholder */ }
  finally { generating.value = false }
}

function handleExportPDF() {
  const w = window.open('', '_blank')
  if (!w) return
  const dim = PAGE_DIMS[pageSize.value]
  w.document.write(`<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Cheatsheet</title>
<style>
  @page { size: ${dim.w}mm ${dim.h}mm; margin: ${marginMm.value}mm; }
  body { font-family: 'Inter','PingFang SC','Microsoft YaHei',sans-serif;
    font-size: ${fontSizePx.value}px; line-height: 1.35; color: #222;
    column-count: ${columns.value}; column-gap: 12px; margin: 0; padding: 0; }
  ${CONTENT_CSS}
</style></head><body>${renderedHtml.value}</body></html>`)
  w.document.close()
  w.onload = () => { w.print() }
}

function handleClose() { visible.value = false }
</script>

<style scoped>
.cheatsheet-dialog :deep(.el-dialog__body) {
  padding: 0;
  height: calc(90vh - 100px);
  overflow: hidden;
}
.cheatsheet-body { display: flex; height: 100%; }

.settings-panel {
  width: 260px; flex-shrink: 0; padding: 20px;
  border-right: 1px solid var(--border-subtle);
  overflow-y: auto; background: var(--bg-sidebar);
}
.panel-title { margin: 0 0 16px; font-size: 15px; font-weight: 600; }
.setting-item { margin-bottom: 16px; }
.setting-item > label { display: block; font-size: 13px; color: var(--text-secondary); margin-bottom: 6px; }
.setting-item :deep(.el-select) { width: 100%; }
.page-indicator { text-align: center; font-size: 12px; color: var(--text-tertiary); margin-top: 8px; }

.preview-panel {
  flex: 1; overflow: auto; background: #e8e8e8;
  display: flex; justify-content: center; padding: 24px;
  position: relative;
}

.edit-area { width: 100%; }
.markdown-editor {
  width: 100%; height: 100%; min-height: 500px;
  border: none; resize: none; font-family: 'Courier New', monospace;
  font-size: 13px; line-height: 1.5; padding: 20px;
  background: white; border-radius: 4px; outline: none; color: var(--text-primary);
}

.paper-wrapper {
  display: flex; flex-direction: column; align-items: center; width: 100%;
}

/* 隐藏的测量容器 */
.measure-box { position: absolute; visibility: hidden; pointer-events: none; z-index: -1; }

/* 页面堆叠 */
.pages-stack {
  display: flex; flex-direction: column; align-items: center; gap: 24px;
}

/* 单页外框 */
.page-sheet {
  background: white;
  box-shadow: 0 2px 12px rgba(0,0,0,0.15);
  border-radius: 2px;
  flex-shrink: 0;
}
.page-num {
  position: absolute; bottom: 4px; right: 8px;
  font-size: 10px; color: #bbb;
}

/* 内容裁剪窗口 */
.page-clip { overflow: hidden; }

/* 内容切片（使用 scoped 的 :deep 穿透内容样式） */
.page-slice :deep(h1) { font-size: 1.3em; margin: 0.3em 0 0.2em; }
.page-slice :deep(h2) { font-size: 1.15em; margin: 0.4em 0 0.2em; border-bottom: 1px solid #ccc; padding-bottom: 2px; }
.page-slice :deep(h3) { font-size: 1.05em; margin: 0.3em 0 0.15em; }
.page-slice :deep(ul), .page-slice :deep(ol) { margin: 0.15em 0; padding-left: 1.3em; }
.page-slice :deep(li) { margin: 0.05em 0; }
.page-slice :deep(p) { margin: 0.15em 0; }
.page-slice :deep(code) { background: #f0f0f0; padding: 1px 3px; border-radius: 2px; font-size: 0.9em; }
.page-slice :deep(pre) { background: #f6f6f6; padding: 6px; border-radius: 4px; overflow-x: auto; font-size: 0.85em; }
.page-slice :deep(blockquote) { border-left: 3px solid #ddd; margin: 0.3em 0; padding-left: 8px; color: #666; }
.page-slice :deep(.cs-page-img) { max-width: 100%; height: auto; margin: 4px 0; border: 1px solid #ddd; border-radius: 4px; }
</style>
