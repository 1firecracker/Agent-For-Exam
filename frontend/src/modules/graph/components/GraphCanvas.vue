<template>
  <div class="graph-canvas-container">
    <div ref="cyContainer" class="cy-container"></div>
    
    <div class="graph-toolbar">
      <el-button-group>
        <el-button :icon="ZoomIn" @click="handleZoomIn" size="small" title="放大" />
        <el-button :icon="ZoomOut" @click="handleZoomOut" size="small" title="缩小" />
        <el-button :icon="FullScreen" @click="handleFullscreen" size="small" title="全屏显示">全屏</el-button>
        <el-button :icon="FullScreen" @click="handleFit" size="small" title="适应画布">适应</el-button>
      </el-button-group>
    </div>
    
    <el-card 
      v-if="selectedEntity" 
      class="node-details-panel"
      shadow="always"
    >
      <template #header>
        <div class="panel-header">
          <span>实体详情</span>
          <el-button text @click="closeDetails" :icon="Close" />
        </div>
      </template>
      <div v-if="entityDetails" class="details-content">
        <div class="detail-item">
          <label>名称：</label>
          <span>{{ entityDetails.name || entityDetails.entity_id }}</span>
        </div>
        <div class="detail-item">
          <label>类型：</label>
          <el-tag size="small">{{ entityDetails.type || '未知' }}</el-tag>
        </div>
        <div class="detail-item" v-if="entityDetails.description">
          <label>描述：</label>
          <p class="description-text">{{ entityDetails.description }}</p>
        </div>
        <div class="detail-item" v-if="entityDetails.source_documents && entityDetails.source_documents.length > 0">
          <label>来源文档：</label>
          <div class="source-documents">
            <el-tag
              v-for="doc in entityDetails.source_documents"
              :key="doc.file_id"
              size="small"
              type="info"
              class="source-doc-tag"
              @click="handleDocClick(doc)"
            >
              {{ doc.filename }}
            </el-tag>
          </div>
        </div>
      </div>
      <div v-else class="loading-details">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
    </el-card>
    
    <el-card 
      v-if="selectedRelation" 
      class="node-details-panel"
      shadow="always"
    >
      <template #header>
        <div class="panel-header">
          <span>关系详情</span>
          <el-button text @click="closeDetails" :icon="Close" />
        </div>
      </template>
      <div v-if="relationDetails" class="details-content">
        <div class="detail-item">
          <label>源实体：</label>
          <span>{{ relationDetails.source }}</span>
        </div>
        <div class="detail-item">
          <label>目标实体：</label>
          <span>{{ relationDetails.target }}</span>
        </div>
        <div class="detail-item">
          <label>关系类型：</label>
          <el-tag size="small">{{ relationDetails.type || '未知' }}</el-tag>
        </div>
        <div class="detail-item" v-if="relationDetails.description">
          <label>描述：</label>
          <p class="description-text">{{ relationDetails.description }}</p>
        </div>
      </div>
      <div v-else class="loading-details">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
    </el-card>
    
    <el-empty 
      v-if="!loading && !cy && (!graphStore.entities || graphStore.entities.length === 0)" 
      description="暂无知识图谱数据"
      :image-size="120"
    />
    
    <div v-if="loading" class="loading-overlay">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载中...</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import cytoscape from 'cytoscape'
import { ZoomIn, ZoomOut, FullScreen, Close, Loading } from '@element-plus/icons-vue'
import { useGraphStore } from '../store/graphStore'

const props = defineProps({
  conversationId: {
    type: String,
    default: null
  },
  filterOptions: {
    type: Object,
    default: () => ({
      searchText: '',
      selectedTypes: [],
      minDegree: 0
    })
  }
})

const emit = defineEmits(['node-click', 'node-hover', 'edge-click', 'doc-click', 'fullscreen'])

const cyContainer = ref(null)
const cy = ref(null)
const loading = ref(false)
const selectedEntity = ref(null)
const entityDetails = ref(null)
const selectedRelation = ref(null)
const relationDetails = ref(null)
const graphStore = useGraphStore()

const calculateNodeDegrees = (entities, relations) => {
  const degreeMap = new Map()
  entities.forEach(entity => {
    degreeMap.set(entity.entity_id || entity.name, 0)
  })
  
  relations.forEach(relation => {
    const source = relation.source
    const target = relation.target
    degreeMap.set(source, (degreeMap.get(source) || 0) + 1)
    degreeMap.set(target, (degreeMap.get(target) || 0) + 1)
  })
  
  return degreeMap
}

const filterGraphData = (entities, relations, filterOptions) => {
  if (!filterOptions) return { entities, relations }
  
  const { searchText = '', selectedTypes = [], minDegree = 0 } = filterOptions
  
  const degreeMap = calculateNodeDegrees(entities, relations)
  
  let filteredEntities = entities.filter(entity => {
    const entityId = entity.entity_id || entity.name
    const entityName = entity.name || entity.entity_id
    const entityType = (entity.type || 'unknown').toLowerCase()
    
    if (searchText && !entityName.toLowerCase().includes(searchText.toLowerCase())) {
      return false
    }
    
    if (selectedTypes.length > 0 && !selectedTypes.includes(entityType)) {
      return false
    }
    
    const degree = degreeMap.get(entityId) || 0
    if (degree < minDegree) {
      return false
    }
    
    return true
  })
  
  const filteredEntityIds = new Set(filteredEntities.map(e => e.entity_id || e.name))
  const filteredRelations = relations.filter(relation => {
    return filteredEntityIds.has(relation.source) && filteredEntityIds.has(relation.target)
  })
  
  return { entities: filteredEntities, relations: filteredRelations }
}

const convertToCytoscapeData = (entities, relations, filterOptions = null) => {
  const { entities: filteredEntities, relations: filteredRelations } = 
    filterOptions ? filterGraphData(entities, relations, filterOptions) : { entities, relations }
  
  const nodes = filteredEntities.map(entity => ({
    data: {
      id: entity.entity_id || entity.name,
      label: entity.name || entity.entity_id,
      type: entity.type || 'unknown',
      description: entity.description || '',
      entityData: entity
    }
  }))
  
  const edges = filteredRelations.map(relation => ({
    data: {
      id: relation.relation_id || `${relation.source}-${relation.target}`,
      source: relation.source,
      target: relation.target,
      label: relation.type || '',
      description: relation.description || '',
      relationData: relation
    }
  }))
  
  return { nodes, edges }
}

const initCytoscape = () => {
  if (!cyContainer.value) return
  
  if (cy.value) {
    cy.value.destroy()
  }
  
  const entities = graphStore.entities || []
  const relations = graphStore.relations || []
  
  if (entities.length === 0) {
    return
  }
  
  const { nodes, edges } = convertToCytoscapeData(entities, relations, props.filterOptions)
  
  const colorMap = {
    'chapterconcept': '#409EFF',
    'definition': '#67C23A',
    'method': '#E6A23C',
    'application': '#F56C6C',
    'example': '#909399',
    'concept': '#409EFF',
    'person': '#67C23A',
    'location': '#E6A23C',
    'organization': '#F56C6C',
    'time': '#9C27B0',
    'event': '#FF9800',
    'object': '#00BCD4',
    'unknown': '#A0CFFF'
  }
  
  const getNodeColor = (type) => {
    if (!type) return colorMap.unknown
    const lowerType = type.toLowerCase()
    if (colorMap[lowerType]) return colorMap[lowerType]
    if (lowerType.includes('concept')) return colorMap.concept
    if (lowerType.includes('person') || lowerType.includes('人')) return colorMap.person
    if (lowerType.includes('location') || lowerType.includes('地点')) return colorMap.location
    if (lowerType.includes('organization') || lowerType.includes('组织')) return colorMap.organization
    if (lowerType.includes('time') || lowerType.includes('时间')) return colorMap.time
    if (lowerType.includes('event') || lowerType.includes('事件')) return colorMap.event
    let hash = 0
    for (let i = 0; i < lowerType.length; i++) {
      hash = lowerType.charCodeAt(i) + ((hash << 5) - hash)
    }
    const hue = hash % 360
    return `hsl(${hue}, 70%, 50%)`
  }
  
  cy.value = cytoscape({
    container: cyContainer.value,
    elements: [...nodes, ...edges],
    style: [
      {
        selector: 'node',
        style: {
          'background-color': (ele) => getNodeColor(ele.data('type')),
          'label': 'data(label)',
          'text-valign': 'center',
          'text-halign': 'center',
          'color': '#fff',
          'font-weight': 'bold',
          'text-outline-width': 1.5,
          'text-outline-color': '#333',
          'width': (ele) => {
            const label = ele.data('label') || '';
            return Math.min(140, Math.max(60, label.length * 10 + 40));
          },
          'height': (ele) => {
            const label = ele.data('label') || '';
            return Math.min(140, Math.max(60, label.length * 10 + 40));
          },
          'font-size': (ele) => {
            const label = ele.data('label') || '';
            const size = Math.min(140, Math.max(60, label.length * 10 + 40));
            const baseSize = size / 5; 
            return Math.min(14, Math.max(10, baseSize - (label.length * 0.2))); 
          },
          'shape': 'ellipse',
          'border-width': 2,
          'border-color': '#fff',
          'text-wrap': 'wrap',
          'text-max-width': (ele) => {
             const label = ele.data('label') || '';
             const width = Math.min(140, Math.max(60, label.length * 10 + 40));
             return width * 0.9;
          }
        }
      },
      {
        selector: 'node:selected',
        style: {
          'border-width': 4,
          'border-color': '#FFD700',
          'background-opacity': 0.8
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': '#999',
          'target-arrow-color': '#999',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'label': 'data(label)',
          'text-rotation': 'autorotate',
          'text-margin-y': -10,
          'font-size': '10px',
          'color': '#666'
        }
      },
      {
        selector: 'edge:selected',
        style: {
          'width': 4,
          'line-color': '#409EFF',
          'target-arrow-color': '#409EFF'
        }
      }
    ],
    layout: {
      name: 'cose',
      animate: true,
      animationDuration: 1000,
      fit: true,
      padding: 30,
      nodeRepulsion: function( node ){ return 4096; },
      idealEdgeLength: function( edge ){ return 100; },
      edgeElasticity: function( edge ){ return 32; },
      nestingFactor: 1.2,
      gravity: 1,
      numIter: 1000,
      initialTemp: 1000,
      coolingFactor: 0.99,
      minTemp: 1.0,
      randomize: true
    },
    userPanningEnabled: true,
    userZoomingEnabled: true,
    boxSelectionEnabled: true
  })
  
  setupEvents()
}

const setupEvents = () => {
  if (!cy.value) return
  
  cy.value.on('tap', 'node', (event) => {
    const node = event.target
    const entityData = node.data('entityData')
    
    if (entityData) {
      selectedEntity.value = entityData
      selectedRelation.value = null
      relationDetails.value = null
      loadEntityDetails(entityData.entity_id || entityData.name)
      emit('node-click', entityData)
    }
  })
  
  cy.value.on('tap', 'edge', (event) => {
    const edge = event.target
    const relationData = edge.data('relationData')
    
    if (relationData) {
      selectedRelation.value = relationData
      selectedEntity.value = null
      entityDetails.value = null
      loadRelationDetails(relationData.source, relationData.target)
      emit('edge-click', relationData)
    }
  })
  
  cy.value.on('mouseover', 'node', (event) => {
    const node = event.target
    node.style('border-width', 4)
    node.style('border-color', '#FFD700')
    
    node.connectedEdges().style('width', 4)
    node.connectedEdges().style('line-color', '#409EFF')
    
    node.neighborhood('node').style('opacity', 0.8)
    
    cy.value.elements().difference(node.union(node.neighborhood())).style('opacity', 0.3)
  })
  
  cy.value.on('mouseout', 'node', (event) => {
    const node = event.target
    
    if (!node.selected()) {
      node.style('border-width', 2)
      node.style('border-color', '#fff')
    }
    
    node.connectedEdges().style('width', 2)
    node.connectedEdges().style('line-color', '#999')
    
    cy.value.elements().style('opacity', 1)
  })
  
  cy.value.on('tap', (event) => {
    if (event.target === cy.value) {
      cy.value.elements().unselect()
      selectedEntity.value = null
      entityDetails.value = null
      selectedRelation.value = null
      relationDetails.value = null
    }
  })
}

const loadEntityDetails = async (entityId) => {
  if (!props.conversationId || !entityId) return
  
  entityDetails.value = null
  
  try {
    const details = await graphStore.getEntity(props.conversationId, entityId)
    entityDetails.value = details
  } catch (error) {
    console.error('加载实体详情失败:', error)
  }
}
  
const loadRelationDetails = async (source, target) => {
  if (!props.conversationId || !source || !target) return
  
  relationDetails.value = null
  
  try {
    const details = await graphStore.getRelation(props.conversationId, source, target)
    relationDetails.value = details
  } catch (error) {
    console.error('加载关系详情失败:', error)
  }
}
  
const handleDocClick = (doc) => {
  emit('doc-click', doc)
}

const handleZoomIn = () => {
  if (cy.value) {
    cy.value.zoom(cy.value.zoom() * 1.2)
  }
}

const handleZoomOut = () => {
  if (cy.value) {
    cy.value.zoom(cy.value.zoom() * 0.8)
  }
}

const handleFullscreen = () => {
  emit('fullscreen')
}

const handleFit = () => {
  if (cy.value) {
    cy.value.fit()
  }
}

const closeDetails = () => {
  selectedEntity.value = null
  entityDetails.value = null
  selectedRelation.value = null
  relationDetails.value = null
  if (cy.value) {
    cy.value.elements().unselect()
  }
}

watch(
  () => [graphStore.entities, graphStore.relations],
  () => {
    if (graphStore.entities && graphStore.entities.length > 0) {
      nextTick(() => {
        initCytoscape()
      })
    }
  },
  { deep: true }
)

watch(
  () => props.filterOptions,
  () => {
    if (graphStore.entities && graphStore.entities.length > 0) {
      nextTick(() => {
        initCytoscape()
      })
    }
  },
  { deep: true }
)

watch(
  () => props.conversationId,
  async (newId) => {
    if (newId) {
      loading.value = true
      try {
        await graphStore.loadGraph(newId)
      } catch (error) {
        console.error('加载图谱失败:', error)
      } finally {
        loading.value = false
      }
    } else {
      graphStore.clearGraph()
      if (cy.value) {
        cy.value.destroy()
        cy.value = null
      }
    }
  },
  { immediate: true }
)

onMounted(async () => {
  if (props.conversationId) {
    loading.value = true
    try {
      await graphStore.loadGraph(props.conversationId)
    } catch (error) {
      console.error('加载图谱失败:', error)
    } finally {
      loading.value = false
    }
  }
})

onUnmounted(() => {
  if (cy.value) {
    cy.value.destroy()
  }
})
</script>

<style scoped>
.graph-canvas-container {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 600px;
  background-color: #f5f5f5;
  flex: 1;
}

.cy-container {
  width: 100%;
  height: 100%;
  min-height: 600px;
  flex: 1;
}

.graph-toolbar {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 100;
  background-color: rgba(255, 255, 255, 0.9);
  padding: 8px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.node-details-panel {
  position: absolute;
  top: 10px;
  left: 10px;
  width: 300px;
  max-height: 400px;
  z-index: 100;
  overflow-y: auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.details-content {
  padding: 0;
}

.detail-item {
  margin-bottom: 12px;
}

.detail-item label {
  font-weight: bold;
  color: #606266;
  display: inline-block;
  min-width: 60px;
}

.detail-item p {
  margin: 4px 0 0 0;
  color: #303133;
  line-height: 1.5;
}

.loading-details {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #909399;
}

.description-text {
  white-space: pre-wrap;
  line-height: 1.5;
  margin: 0;
}

.source-documents {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.source-doc-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.source-doc-tag:hover {
  transform: scale(1.05);
  opacity: 0.8;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background-color: rgba(255, 255, 255, 0.8);
  z-index: 200;
  color: #909399;
}

.loading-overlay .el-icon {
  font-size: 32px;
}
</style>


