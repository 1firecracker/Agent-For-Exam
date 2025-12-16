<template>
  <el-card class="mindmap-viewer-card">
    <template #header>
      <div class="viewer-header">
        <div class="header-left">
          <h3>思维脑图</h3>
          <el-text v-if="mindmapStore.hasMindMap" class="mindmap-stats">
            {{ mindmapStore.mindmapContent.split('\n').length }} 行
          </el-text>
        </div>
        <div class="header-right">
          <el-button 
            :icon="Expand" 
            circle 
            plain 
            size="small" 
            @click="handleExpandAll"
            :disabled="!markmapInstance || !mindmapStore.hasMindMap"
            :title="expandMode === 'all' ? '恢复初始状态' : '全部展开'"
          >
          </el-button>
          <el-button 
            :icon="Refresh" 
            circle 
            plain 
            size="small" 
            @click="handleRefresh"
            :loading="mindmapStore.loading"
            title="刷新脑图"
          />
          <el-dropdown @command="handleExport" trigger="click">
            <el-button 
              circle 
              plain 
              size="small" 
              title="导出思维脑图"
            >
              <el-icon><Download /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="svg">导出为 SVG</el-dropdown-item>
                <el-dropdown-item command="xmind">导出为 XMind</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button 
            :icon="FullScreen" 
            circle 
            plain 
            size="small" 
            @click="handleFullscreen"
            title="全屏查看"
          />
        </div>
      </div>
    </template>
    
    <!-- 思维脑图容器 -->
    <div class="mindmap-container">
      <!-- 加载中 -->
      <div v-if="mindmapStore.loading" class="mindmap-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
      
      <!-- 错误提示 -->
      <el-alert
        v-else-if="mindmapStore.error"
        :title="mindmapStore.error.message || '加载失败'"
        type="error"
        :closable="false"
        show-icon
      />
      
      <!-- 生成中或已有内容：显示思维脑图容器（支持流式实时显示） -->
      <div v-else-if="mindmapStore.generating || mindmapStore.mindmapContent" class="mindmap-wrapper">
        <!-- 生成中时显示进度条（覆盖在思维脑图上方） -->
        <div v-if="mindmapStore.generating" class="generating-overlay">
          <el-progress 
            :percentage="generationProgress" 
            :status="generationProgress === 100 ? 'success' : ''"
            :stroke-width="6"
            :show-text="true"
          />
          <div class="generating-text">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>正在生成思维脑图...</span>
          </div>
        </div>
        
        <!-- 思维脑图渲染容器 -->
        <div 
          ref="mindmapContainer"
          class="mindmap-canvas"
          :class="{ 'generating': mindmapStore.generating }"
        />
      </div>
      
      <!-- 空状态 -->
      <el-empty
        v-else
        description="暂无思维脑图，上传文档后将自动生成"
        :image-size="120"
      />
    </div>
    
    <!-- 全屏弹窗 -->
    <el-dialog
      v-model="fullscreenVisible"
      title="思维脑图 - 全屏视图"
      width="95%"
      :close-on-click-modal="false"
      :close-on-press-escape="true"
      class="mindmap-fullscreen-dialog"
    >
      <div ref="fullscreenContainer" class="fullscreen-mindmap-container" />
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Refresh, FullScreen, Loading, Expand, Download } from '@element-plus/icons-vue'
import { useMindMapStore } from '../store/mindmapStore'
import { useConversationStore } from '../../chat/store/conversationStore'
import { useDocumentStore } from '../../documents/store/documentStore'

import { Markmap } from 'markmap-view'
import { Transformer } from 'markmap-lib'

const mindmapStore = useMindMapStore()
const convStore = useConversationStore()
const docStore = useDocumentStore()

const mindmapContainer = ref(null)
const fullscreenContainer = ref(null)
const fullscreenVisible = ref(false)
const generationProgress = ref(0)

const markmapInstance = ref(null)
let fullscreenMarkmapInstance = null
let renderDebounceTimer = null
let renderRAFId = null
let skipNextRender = false
const processingDocs = new Set()
const expandMode = ref('default')

let transformer = null
const getTransformer = () => {
  if (!Transformer) {
    console.error('Transformer 类未加载')
    return null
  }
  if (!transformer) {
    try {
      transformer = new Transformer()
    } catch (error) {
      console.error('创建 Transformer 实例失败:', error)
      return null
    }
  }
  return transformer
}

const renderMindMap = async (container, content) => {
  if (!container || !content) {
    return
  }
  
  if (!Markmap) {
    console.warn('Markmap 未加载，无法渲染思维脑图')
    return
  }
  
  if (!Transformer) {
    console.warn('Transformer 未加载，无法解析 Markdown')
    return
  }

  try {
    const transformer = getTransformer()
    if (!transformer) {
      console.error('无法创建 Transformer 实例')
      return
    }
    
    const result = transformer.transform(content)
    if (!mindmapStore.generating) {
      console.log('📊 Transformer 解析结果:', result)
    }
    
    let root = result.root
    
    if (!root) {
      console.warn('Markdown 解析结果为空', result)
      return
    }
    
    if (!root.content && !root.children) {
      if (!mindmapStore.generating) {
        console.warn('⚠️ root 数据格式异常，可能不是有效的思维导图数据:', root)
      }
      const altRoot = result.root || result
      if (altRoot && (altRoot.content || altRoot.children)) {
        if (!mindmapStore.generating) {
          console.log('🔄 使用替代 root 数据')
        }
        root = altRoot
      }
    }
    
    const decodeHtmlEntities = (obj) => {
      if (typeof obj === 'string') {
        const textarea = document.createElement('textarea')
        textarea.innerHTML = obj
        return textarea.value
      } else if (Array.isArray(obj)) {
        return obj.map(decodeHtmlEntities)
      } else if (obj && typeof obj === 'object') {
        const decoded = { ...obj }
        if (decoded.content) {
          decoded.content = decodeHtmlEntities(decoded.content)
        }
        if (decoded.children) {
          decoded.children = decodeHtmlEntities(decoded.children)
        }
        return decoded
      }
      return obj
    }
    
    root = decodeHtmlEntities(root)
    
    if (!mindmapStore.generating) {
      console.log('📊 解析后的 root 数据:', root)
      console.log('📊 root 类型:', typeof root)
      console.log('📊 root 键:', Object.keys(root || {}))
    }
    
    let instance = null
    const options = {
      color: (node) => {
        const depth = node.depth || 0
        const colors = [
          '#409eff',
          '#67c23a',
          '#e6a23c',
          '#f56c6c',
          '#909399'
        ]
        return colors[Math.min(depth, colors.length - 1)]
      },
      duration: 300,
      maxWidth: 300,
      initialExpandLevel: expandMode.value === 'all' ? Infinity : 4,
    }
    
    if (container === mindmapContainer.value) {
      if (!markmapInstance.value) {
        console.log('🆕 创建新的 markmap 实例（主容器）')
        container.innerHTML = ''
        const svgElement = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
        svgElement.setAttribute('width', '100%')
        svgElement.setAttribute('height', '100%')
        svgElement.style.display = 'block'
        container.appendChild(svgElement)
        markmapInstance.value = Markmap.create(svgElement, options)
      }
      instance = markmapInstance.value
    } else if (container === fullscreenContainer.value) {
      if (!fullscreenMarkmapInstance) {
        console.log('🆕 创建新的 markmap 实例（全屏容器）')
        container.innerHTML = ''
        const svgElement = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
        svgElement.setAttribute('width', '100%')
        svgElement.setAttribute('height', '100%')
        svgElement.style.display = 'block'
        container.appendChild(svgElement)
        fullscreenMarkmapInstance = Markmap.create(svgElement, options)
      }
      instance = fullscreenMarkmapInstance
    }

    if (instance) {
      if (!mindmapStore.generating) {
        console.log('🔄 更新 markmap 数据，root:', root)
        console.log('📐 容器尺寸:', container.offsetWidth, 'x', container.offsetHeight)
      }
      
      if (container.offsetWidth === 0 || container.offsetHeight === 0) {
        console.warn('⚠️ 容器尺寸为 0，等待容器渲染...')
        setTimeout(() => {
          if (container.offsetWidth > 0 && container.offsetHeight > 0) {
            instance.setData(root)
            instance.fit()
            console.log('✅ 思维脑图渲染成功（延迟）')
          }
        }, 300)
        return
      }
      
      try {
        instance.setData(root)
        if (typeof instance.fit === 'function') {
          instance.fit()
        }
        if (!mindmapStore.generating) {
          console.log('✅ 思维脑图数据更新成功')
        }
        return
      } catch (error) {
        console.error('❌ 更新数据失败，尝试重新创建实例:', error)
        const existingSvg = container.querySelector('svg')
        if (existingSvg) {
          existingSvg.remove()
        }
        Array.from(container.children).forEach(child => {
          if (child.tagName !== 'SVG') {
            child.remove()
          }
        })
        
        container.innerHTML = ''
        const svgElement = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
        svgElement.setAttribute('width', '100%')
        svgElement.setAttribute('height', '100%')
        svgElement.style.display = 'block'
        container.appendChild(svgElement)
        
        if (container === mindmapContainer.value) {
          if (markmapInstance.value) {
            try {
              markmapInstance.value.destroy?.()
            } catch (e) {
              console.warn('销毁旧实例失败:', e)
            }
          }
          markmapInstance.value = Markmap.create(svgElement, options)
          instance = markmapInstance.value
        } else if (container === fullscreenContainer.value) {
          if (fullscreenMarkmapInstance) {
            try {
              fullscreenMarkmapInstance.destroy?.()
            } catch (e) {
              console.warn('销毁旧实例失败:', e)
            }
          }
          fullscreenMarkmapInstance = Markmap.create(svgElement, options)
          instance = fullscreenMarkmapInstance
        }
        
        console.log('✅ Markmap 实例已重新创建，SVG 元素:', svgElement)
        
        if (instance) {
          try {
            instance.setData(root)
            console.log('✅ setData 调用成功')
          } catch (error) {
            console.error('❌ setData 调用失败:', error)
            return
          }
          
          if (typeof instance.fit === 'function') {
            try {
              instance.fit()
              console.log('✅ fit 调用成功')
            } catch (error) {
              console.error('❌ fit 调用失败:', error)
            }
          }
        }
      }
    } else {
      console.warn('⚠️ 无法创建 markmap 实例，container:', container)
    }
  } catch (error) {
    console.error('渲染思维脑图失败:', error)
  }
}

watch(() => mindmapStore.mindmapContent, async (newContent, oldContent) => {
  if (skipNextRender) {
    skipNextRender = false
    return
  }
  if (newContent && newContent.trim()) {
    if (renderDebounceTimer) {
      clearTimeout(renderDebounceTimer)
      renderDebounceTimer = null
    }
    if (renderRAFId) {
      cancelAnimationFrame(renderRAFId)
      renderRAFId = null
    }
    
    const hasValidContent = newContent.includes('##') || newContent.includes('#') || newContent.includes('-')
    
    if (!hasValidContent) {
      return
    }
    
    const debounceTime = mindmapStore.generating ? 50 : 300
    
    renderDebounceTimer = setTimeout(() => {
      renderRAFId = requestAnimationFrame(async () => {
        await nextTick()
        
        if (mindmapContainer.value && Markmap && Transformer) {
          if (!mindmapStore.generating) {
            console.log('🔄 流式更新思维脑图，内容长度:', newContent.length)
          }
          renderMindMap(mindmapContainer.value, newContent)
        }
        if (fullscreenVisible.value && fullscreenContainer.value && Markmap && Transformer) {
          renderMindMap(fullscreenContainer.value, newContent)
        }
        
        renderRAFId = null
      })
      
      renderDebounceTimer = null
    }, debounceTime)
  } else if (!newContent && oldContent) {
    if (renderDebounceTimer) {
      clearTimeout(renderDebounceTimer)
      renderDebounceTimer = null
    }
    if (renderRAFId) {
      cancelAnimationFrame(renderRAFId)
      renderRAFId = null
    }
    
    if (mindmapContainer.value) {
      mindmapContainer.value.innerHTML = ''
    }
    if (fullscreenContainer.value) {
      fullscreenContainer.value.innerHTML = ''
    }
    markmapInstance.value = null
    fullscreenMarkmapInstance = null
  }
}, { immediate: true })

watch(() => convStore.currentConversationId, async (newId, oldId) => {
  if (newId) {
    console.log('🔄 对话变化，自动加载思维脑图:', newId)
    try {
      await mindmapStore.loadMindMap(newId)
      await nextTick()
      if (mindmapStore.mindmapContent && mindmapContainer.value && Markmap && Transformer) {
        setTimeout(async () => {
          await renderMindMap(mindmapContainer.value, mindmapStore.mindmapContent)
        }, 300)
      }
    } catch (error) {
      console.error('对话变化时加载思维脑图失败:', error)
    }
  } else {
    mindmapStore.clearMindMap()
    if (markmapInstance.value) {
      markmapInstance.value = null
    }
    if (fullscreenMarkmapInstance) {
      fullscreenMarkmapInstance = null
    }
  }
}, { immediate: true })

watch(() => docStore.extractionProgress, async (progress, oldProgress) => {
  if (!convStore.currentConversationId) {
    console.log('⚠️ 没有当前对话ID，跳过思维脑图生成')
    return
  }
  
  const convId = convStore.currentConversationId
  const currentProgress = progress[convId] || {}
  const oldProgressData = oldProgress?.[convId] || {}
  
  console.log('📊 文档状态变化:', {
    currentProgress: Object.keys(currentProgress).length,
    oldProgress: oldProgressData ? Object.keys(oldProgressData).length : 0,
    currentStatuses: Object.entries(currentProgress).map(([id, data]) => ({ id: id.substring(0, 8), status: data.status }))
  })
  
  let hasNewProcessing = false
  let processingDocId = null
  for (const [docId, docData] of Object.entries(currentProgress)) {
    const oldDocData = oldProgressData[docId]
    const oldStatus = oldDocData?.status || 'unknown'
    const newStatus = docData.status
    
    console.log(`📋 文档 ${docId.substring(0, 8)}... 状态: ${oldStatus} -> ${newStatus}`)
    
    if (newStatus === 'processing' && oldStatus !== 'processing') {
      hasNewProcessing = true
      processingDocId = docId
      console.log(`✅ 检测到文档开始处理: ${docId.substring(0, 8)}...`)
      break
    }
  }
  
  if (hasNewProcessing && processingDocId) {
    console.log('🔍 检查是否可以启动流式生成:', {
      hasNewProcessing,
      processingDocId: processingDocId.substring(0, 8),
      alreadyProcessing: processingDocs.has(processingDocId),
      generating: mindmapStore.generating,
      loading: mindmapStore.loading
    })
    
    if (!processingDocs.has(processingDocId) &&
        !mindmapStore.generating && 
        !mindmapStore.loading) {
      console.log('🚀 启动流式生成思维脑图，文档ID:', processingDocId.substring(0, 8))
      
      processingDocs.add(processingDocId)
      
      try {
        console.log('📡 调用流式生成 API...')
        await mindmapStore.generateMindMap(convId, processingDocId, (content) => {
          if (content) {
            const estimatedProgress = Math.min(95, Math.floor((content.length / 5000) * 100))
            generationProgress.value = estimatedProgress
            console.log(`📈 流式生成进度: ${estimatedProgress}%, 内容长度: ${content.length}`)
          }
        })
        
        generationProgress.value = 100
        console.log('✅ 流式生成思维脑图完成')
      } catch (error) {
        console.error('❌ 流式生成思维脑图失败:', error)
        console.error('错误详情:', error.message, error.stack)
        generationProgress.value = 0
      } finally {
        processingDocs.delete(processingDocId)
        console.log('🧹 清理处理标记')
      }
    } else {
      console.log('⏸️ 跳过流式生成，原因:', {
        alreadyProcessing: processingDocs.has(processingDocId),
        generating: mindmapStore.generating,
        loading: mindmapStore.loading
      })
    }
  }
  
  let hasNewCompleted = false
  for (const [docId, docData] of Object.entries(currentProgress)) {
    const oldDocData = oldProgressData[docId]
    if (docData.status === 'completed' && 
        (!oldDocData || oldDocData.status !== 'completed')) {
      hasNewCompleted = true
      break
    }
  }
  
  if (hasNewCompleted && 
      !mindmapStore.generating && 
      !mindmapStore.loading && 
      !mindmapStore.hasMindMap) {
    console.log('🔄 检测到文档处理完成，但思维脑图未生成，尝试从文件加载...')
    setTimeout(async () => {
      try {
        await mindmapStore.loadMindMap(convId)
        await nextTick()
        if (mindmapStore.mindmapContent && mindmapContainer.value && Markmap && Transformer) {
          setTimeout(async () => {
            await renderMindMap(mindmapContainer.value, mindmapStore.mindmapContent)
          }, 200)
        }
      } catch (error) {
        console.error('从文件加载思维脑图失败:', error)
      }
    }, 2000)
  }
}, { deep: true, immediate: false })

const handleRefresh = async () => {
  console.log('🔄 手动刷新思维脑图')

  if (mindmapContainer.value) {
    try {
      if (markmapInstance.value && typeof markmapInstance.value.destroy === 'function') {
        markmapInstance.value.destroy()
      }
    } catch (e) {
      console.warn('销毁旧 Markmap 实例时出错（忽略）：', e)
    }
    mindmapContainer.value.innerHTML = ''
    markmapInstance.value = null
  }

  if (convStore.currentConversationId) {
    try {
      await mindmapStore.loadMindMap(convStore.currentConversationId)
      console.log('✅ 思维脑图加载完成，内容长度:', mindmapStore.mindmapContent?.length || 0)
      await nextTick()
      if (mindmapStore.mindmapContent && mindmapContainer.value && Markmap && Transformer) {
        console.log('🔄 开始渲染思维脑图...')
        setTimeout(async () => {
          await renderMindMap(mindmapContainer.value, mindmapStore.mindmapContent)
        }, 200)
      } else {
        console.warn('⚠️ 刷新时渲染条件不满足:', {
          hasContent: !!mindmapStore.mindmapContent,
          hasContainer: !!mindmapContainer.value,
          hasMarkmap: !!Markmap,
          hasTransformer: !!Transformer
        })
      }
    } catch (error) {
      console.error('❌ 刷新思维脑图失败:', error)
    }
  } else {
    console.warn('⚠️ 刷新时没有对话ID')
  }
}

const handleExpandAll = () => {
  if (!markmapInstance.value || !mindmapStore.mindmapContent) {
    console.warn('⚠️ markmap 实例或内容不存在，无法切换模式')
    return
  }
  
  const newMode = expandMode.value === 'all' ? 'default' : 'all'
  expandMode.value = newMode
  skipNextRender = true
  
  if (markmapInstance.value) {
    try {
      if (typeof markmapInstance.value.destroy === 'function') {
        markmapInstance.value.destroy()
      }
    } catch (e) {
      console.warn('销毁旧实例失败:', e)
    }
    markmapInstance.value = null
  }
  
  if (mindmapContainer.value) {
    mindmapContainer.value.innerHTML = ''
  }
  
  renderMindMap(mindmapContainer.value, mindmapStore.mindmapContent)
  console.log(`✅ 已切换为${newMode === 'all' ? '全展开' : '初始'}模式，实例已重新创建`)
}

const handleExport = async (format) => {
  if (!markmapInstance.value || !mindmapContainer.value) {
    console.warn('⚠️ markmap 实例或容器不存在，无法导出')
    return
  }
  
  const svgElement = mindmapContainer.value.querySelector('svg')
  if (!svgElement) {
    console.warn('⚠️ 未找到 SVG 元素，无法导出')
    return
  }
  
  const conversationId = convStore.currentConversationId || 'mindmap'
  const timestamp = new Date().toISOString().split('T')[0]
  const filename = `思维脑图_${conversationId}_${timestamp}`
  
  if (format === 'svg') {
    const svgData = new XMLSerializer().serializeToString(svgElement)
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(svgBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${filename}.svg`
    link.click()
    URL.revokeObjectURL(url)
    console.log('✅ SVG 导出成功')
  } else if (format === 'png') {
    const container = mindmapContainer.value
    
    if (!container) {
      console.error('❌ 容器不存在，无法导出')
      return
    }
    
    html2canvas(container, {
      backgroundColor: '#ffffff',
      scale: 5,
      useCORS: true,
      logging: false,
      width: container.scrollWidth,
      height: container.scrollHeight,
      windowWidth: container.scrollWidth,
      windowHeight: container.scrollHeight,
    }).then((canvas) => {
      canvas.toBlob((blob) => {
        if (blob) {
          const url = URL.createObjectURL(blob)
          const link = document.createElement('a')
          link.href = url
          link.download = `${filename}.png`
          link.click()
          URL.revokeObjectURL(url)
          console.log('✅ PNG 导出成功（使用 html2canvas）')
        } else {
          console.error('❌ PNG 导出失败：无法生成 blob')
          alert('PNG 导出失败，请尝试导出为 SVG 格式')
        }
      }, 'image/png', 1.0)
    }).catch((error) => {
      console.error('❌ PNG 导出失败:', error)
      alert('PNG 导出失败，已自动导出为 SVG 格式')
      handleExport('svg')
    })
  } else if (format === 'xmind') {
    try {
      const JSZip = (await import('jszip')).default
      
      const transformer = getTransformer()
      if (!transformer) {
        console.error('❌ Transformer 不可用')
        return
      }
      
      const result = transformer.transform(mindmapStore.mindmapContent)
      const root = result.root
      
      if (!root) {
        console.error('❌ 无法解析思维脑图数据')
        return
      }
      
      const xmindXml = generateXMindXML(root, filename)
      
      const zip = new JSZip()
      zip.file('content.xml', xmindXml)
      zip.file('META-INF/manifest.xml', generateManifestXML())
      
      const blob = await zip.generateAsync({ type: 'blob' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${filename}.xmind`
      link.click()
      URL.revokeObjectURL(url)
      console.log('✅ XMind 导出成功')
    } catch (error) {
      if (error.message && error.message.includes('jszip')) {
        console.error('❌ XMind 导出失败：请先安装 jszip 库')
        console.log('💡 安装命令：npm install jszip')
        alert('XMind 导出需要安装 jszip 库，请运行：npm install jszip')
      } else {
        console.error('❌ XMind 导出失败:', error)
      }
    }
  }
}

const decodeHtmlEntity = (text) => {
  if (!text) return ''
  const textarea = document.createElement('textarea')
  textarea.innerHTML = String(text)
  return textarea.value
}

const generateXMindXML = (root, title) => {
  const convertNode = (node, depth = 0) => {
    let content = node.content || ''
    content = decodeHtmlEntity(content)
    const children = node.children || []
    
    let xml = `<topic id="${Date.now()}-${Math.random()}">`
    xml += `<title><![CDATA[${content}]]></title>`
    
    if (children.length > 0) {
      xml += '<children><topics type="attached">'
      children.forEach(child => {
        xml += convertNode(child, depth + 1)
      })
      xml += '</topics></children>'
    }
    
    xml += '</topic>'
    return xml
  }
  
  let rootContent = root.content || title
  rootContent = decodeHtmlEntity(rootContent)
  const rootChildren = root.children || []
  
  let xml = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
  xml += '<xmap-content xmlns="urn:xmind:xmap:xmlns:content:2.0" xmlns:fo="http://www.w3.org/1999/XSL/Format" xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.0" xsi:schemaLocation="urn:xmind:xmap:xmlns:content:2.0 content.xsd">'
  xml += '<sheet id="root">'
  xml += '<topic id="root-topic">'
  xml += `<title><![CDATA[${rootContent}]]></title>`
  
  if (rootChildren.length > 0) {
    xml += '<children><topics type="attached">'
    rootChildren.forEach(child => {
      xml += convertNode(child)
    })
    xml += '</topics></children>'
  }
  
  xml += '</topic>'
  xml += '</sheet>'
  xml += '</xmap-content>'
  
  return xml
}

const generateManifestXML = () => {
  return `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<manifest xmlns="urn:xmind:xmap:xmlns:manifest:1.0">
  <file-entry full-path="content.xml" media-type="text/xml"/>
  <file-entry full-path="META-INF/" media-type=""/>
  <file-entry full-path="META-INF/manifest.xml" media-type="text/xml"/>
</manifest>`
}

const escapeXml = (text) => {
  if (!text) return ''
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}

const handleFullscreen = async () => {
  fullscreenVisible.value = true
  await nextTick()
  if (fullscreenContainer.value && mindmapStore.mindmapContent) {
    await renderMindMap(fullscreenContainer.value, mindmapStore.mindmapContent)
  }
}

onMounted(async () => {
  console.log('🔄 MindMapViewer 组件挂载')
  if (convStore.currentConversationId) {
    console.log('🔄 组件挂载，自动加载思维脑图，对话ID:', convStore.currentConversationId)
    try {
      await mindmapStore.loadMindMap(convStore.currentConversationId)
      console.log('✅ 思维脑图加载完成，内容长度:', mindmapStore.mindmapContent?.length || 0)
      await nextTick()
      if (mindmapStore.mindmapContent && mindmapContainer.value && Markmap && Transformer) {
        console.log('🔄 开始渲染思维脑图...')
        setTimeout(async () => {
          await renderMindMap(mindmapContainer.value, mindmapStore.mindmapContent)
        }, 300)
      } else {
        console.warn('⚠️ 渲染条件不满足:', {
          hasContent: !!mindmapStore.mindmapContent,
          hasContainer: !!mindmapContainer.value,
          hasMarkmap: !!Markmap,
          hasTransformer: !!Transformer
        })
      }
    } catch (error) {
      console.error('组件挂载时加载思维脑图失败:', error)
    }
  } else {
    console.warn('⚠️ 组件挂载时没有对话ID')
  }
})

onUnmounted(() => {
  if (markmapInstance.value) {
    markmapInstance.value = null
  }
  if (fullscreenMarkmapInstance) {
    fullscreenMarkmapInstance = null
  }
})
</script>

<style scoped>
.mindmap-viewer-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.mindmap-viewer-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.mindmap-stats {
  font-size: 12px;
  color: #909399;
}

.header-right {
  display: flex;
  gap: 8px;
}

.mindmap-container {
  flex: 1;
  position: relative;
  min-height: 400px;
  overflow: hidden;
}

.mindmap-loading,
.mindmap-generating {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  gap: 16px;
}

.generating-text {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #606266;
}

.mindmap-wrapper {
  width: 100%;
  height: 100%;
  min-height: 400px;
  position: relative;
  overflow: hidden;
}

.mindmap-canvas {
  width: 100%;
  height: 100%;
  min-height: 400px;
  position: relative;
  overflow: auto;
  background-color: #fff;
  font-size: 0;
  line-height: 0;
}

.mindmap-canvas.generating {
  opacity: 0.9;
}

.generating-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.8));
  padding: 20px;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  border-radius: 0 0 8px 8px;
}

.mindmap-canvas :deep(svg) {
  width: 100% !important;
  height: 100% !important;
  display: block !important;
  min-height: 400px;
  position: relative;
  z-index: 1;
}

.mindmap-canvas :deep(.markmap) {
  width: 100%;
  height: 100%;
}

.mindmap-canvas :deep(g) {
  display: block;
}

.mindmap-canvas > *:not(svg) {
  display: none !important;
}

.mindmap-fullscreen-dialog :deep(.el-dialog__body) {
  padding: 0;
  height: 80vh;
}

.fullscreen-mindmap-container {
  width: 100%;
  height: 100%;
  min-height: 600px;
}
</style>



