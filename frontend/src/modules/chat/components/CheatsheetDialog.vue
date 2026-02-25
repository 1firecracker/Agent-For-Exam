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
          v-if="markdownContent"
          style="width: 100%; margin-top: 8px; margin-left: 0; border-radius: 8px;"
          @click="handleExportPDF"
        >
          导出 PDF
        </el-button>

        <el-divider v-if="markdownContent" />

        <div v-if="markdownContent" class="setting-item">
          <el-switch v-model="editMode" active-text="编辑模式" />
        </div>
      </div>

      <!-- 右侧预览/编辑区 -->
      <div class="preview-panel">
        <div v-if="!markdownContent && !generating" class="empty-preview">
          <el-empty description="点击左侧「生成 Cheatsheet」按钮" :image-size="100" />
        </div>

        <!-- 编辑模式 -->
        <div v-else-if="editMode" class="edit-area">
          <textarea
            v-model="markdownContent"
            class="markdown-editor"
            placeholder="在此编辑 Markdown 内容..."
          ></textarea>
        </div>

        <!-- 预览模式 -->
        <div v-else class="paper-wrapper">
          <div
            ref="paperRef"
            class="paper"
            :style="paperStyle"
            v-html="renderedHtml"
          ></div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
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
const markdownContent = ref('')
const imageRefs = ref([])

const PAGE_DIMS = {
  A4: { w: 210, h: 297 },
  A3: { w: 297, h: 420 },
  Letter: { w: 216, h: 279 },
}

const paperStyle = computed(() => {
  const dim = PAGE_DIMS[pageSize.value]
  return {
    width: `${dim.w}mm`,
    minHeight: `${dim.h}mm`,
    padding: `${marginMm.value}mm`,
    fontSize: `${fontSizePx.value}px`,
    columnCount: columns.value,
    columnGap: '12px',
  }
})

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

async function handleGenerate() {
  if (!props.subjectId) return
  generating.value = true
  markdownContent.value = ''
  imageRefs.value = []
  editMode.value = false

  try {
    const resp = await fetch(`${BASE_URL}/api/subjects/${props.subjectId}/cheatsheet/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ include_images: includeImages.value }),
    })

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

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
            markdownContent.value += data.content
          } else if (data.image_refs) {
            imageRefs.value = data.image_refs
          } else if (data.error) {
            markdownContent.value += `\n\n> ⚠ 错误: ${data.error}`
          }
        } catch { /* ignore */ }
      }
    }
    if (buffer.trim()) {
      try {
        const data = JSON.parse(buffer)
        if (data.content) markdownContent.value += data.content
      } catch { /* ignore */ }
    }
  } catch (e) {
    markdownContent.value += `\n\n> ⚠ 请求失败: ${e.message}`
  } finally {
    generating.value = false
  }
}

function handleExportPDF() {
  const printWindow = window.open('', '_blank')
  if (!printWindow) return
  const dim = PAGE_DIMS[pageSize.value]
  printWindow.document.write(`<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Cheatsheet</title>
<style>
  @page { size: ${dim.w}mm ${dim.h}mm; margin: ${marginMm.value}mm; }
  body { font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
         font-size: ${fontSizePx.value}px; line-height: 1.35; color: #222;
         column-count: ${columns.value}; column-gap: 12px; margin: 0; padding: 0; }
  h2 { font-size: 1.15em; margin: 0.4em 0 0.2em; border-bottom: 1px solid #ccc; padding-bottom: 2px; }
  h3 { font-size: 1.05em; margin: 0.3em 0 0.15em; }
  ul, ol { margin: 0.15em 0; padding-left: 1.3em; }
  li { margin: 0.05em 0; }
  p { margin: 0.15em 0; }
  .cs-page-img { max-width: 100%; height: auto; margin: 4px 0; border: 1px solid #ddd; border-radius: 4px; }
  code { background: #f0f0f0; padding: 1px 3px; border-radius: 2px; font-size: 0.9em; }
  pre { background: #f6f6f6; padding: 6px; border-radius: 4px; overflow-x: auto; font-size: 0.85em; }
  blockquote { border-left: 3px solid #ddd; margin: 0.3em 0; padding-left: 8px; color: #666; }
</style>
</head><body>${renderedHtml.value}</body></html>`)
  printWindow.document.close()
  printWindow.onload = () => { printWindow.print() }
}

function handleClose() {
  visible.value = false
}
</script>

<style scoped>
.cheatsheet-dialog :deep(.el-dialog__body) {
  padding: 0;
  height: calc(90vh - 100px);
  overflow: hidden;
}

.cheatsheet-body {
  display: flex;
  height: 100%;
}

.settings-panel {
  width: 260px;
  flex-shrink: 0;
  padding: 20px;
  border-right: 1px solid var(--border-subtle);
  overflow-y: auto;
  background: var(--bg-sidebar);
}

.panel-title {
  margin: 0 0 16px;
  font-size: 15px;
  font-weight: 600;
}

.setting-item {
  margin-bottom: 16px;
}

.setting-item > label {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.setting-item :deep(.el-select) {
  width: 100%;
}

.preview-panel {
  flex: 1;
  overflow: auto;
  background: #e8e8e8;
  display: flex;
  justify-content: center;
  padding: 24px;
}

.empty-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}

.edit-area {
  width: 100%;
}

.markdown-editor {
  width: 100%;
  height: 100%;
  min-height: 500px;
  border: none;
  resize: none;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  padding: 20px;
  background: white;
  border-radius: 4px;
  outline: none;
  color: var(--text-primary);
}

.paper-wrapper {
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.paper {
  background: white;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  border-radius: 2px;
  line-height: 1.35;
  color: #222;
  overflow: hidden;
}

.paper :deep(h2) {
  font-size: 1.15em;
  margin: 0.4em 0 0.2em;
  border-bottom: 1px solid #ccc;
  padding-bottom: 2px;
}

.paper :deep(h3) {
  font-size: 1.05em;
  margin: 0.3em 0 0.15em;
}

.paper :deep(ul),
.paper :deep(ol) {
  margin: 0.15em 0;
  padding-left: 1.3em;
}

.paper :deep(li) {
  margin: 0.05em 0;
}

.paper :deep(p) {
  margin: 0.15em 0;
}

.paper :deep(.cs-page-img) {
  max-width: 100%;
  height: auto;
  margin: 4px 0;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.paper :deep(code) {
  background: #f0f0f0;
  padding: 1px 3px;
  border-radius: 2px;
  font-size: 0.9em;
}

.paper :deep(pre) {
  background: #f6f6f6;
  padding: 6px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 0.85em;
}

.paper :deep(blockquote) {
  border-left: 3px solid #ddd;
  margin: 0.3em 0;
  padding-left: 8px;
  color: #666;
}
</style>
