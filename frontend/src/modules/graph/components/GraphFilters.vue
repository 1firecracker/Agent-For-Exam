<template>
  <el-card class="graph-filters-card" shadow="never">
    <template #header>
      <div class="filters-header">
        <span>图谱过滤</span>
        <el-button 
          text 
          type="primary" 
          size="small" 
          @click="handleReset"
          :disabled="!hasFilters"
        >
          重置
        </el-button>
      </div>
    </template>
    
    <div class="filters-content">
      <div class="filter-item">
        <label>搜索实体</label>
        <el-input
          v-model="searchText"
          placeholder="输入实体名称..."
          clearable
          @input="handleSearch"
          @clear="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
      
      <div class="filter-item">
        <label>实体类型</label>
        <el-checkbox-group v-model="selectedTypes" @change="handleTypeFilter">
          <el-checkbox 
            v-for="type in availableTypes" 
            :key="type.value" 
            :label="type.value"
          >
            {{ type.label }}
          </el-checkbox>
        </el-checkbox-group>
      </div>
      
      <div class="filter-item">
        <label>最小连接度</label>
        <el-slider
          v-model="minDegree"
          :min="0"
          :max="maxDegree"
          :step="1"
          show-stops
          :show-tooltip="true"
          @change="handleDegreeFilter"
        />
        <div class="slider-info">
          <span>当前: {{ minDegree }}</span>
          <span>最大: {{ maxDegree }}</span>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { useGraphStore } from '../store/graphStore'

const emit = defineEmits(['filter-change'])

const graphStore = useGraphStore()

const searchText = ref('')
const selectedTypes = ref([])
const minDegree = ref(0)
const maxDegree = ref(10)

const availableTypes = [
  { value: 'chapterconcept', label: '章节概念' },
  { value: 'definition', label: '定义' },
  { value: 'method', label: '方法' },
  { value: 'application', label: '应用' },
  { value: 'example', label: '例子' },
  { value: 'unknown', label: '未知' }
]

const hasFilters = computed(() => {
  return searchText.value.length > 0 || 
         selectedTypes.value.length > 0 || 
         minDegree.value > 0
})

watch(() => graphStore.entities, (entities) => {
  if (entities && entities.length > 0) {
    const degreeMap = new Map()
    graphStore.relations.forEach(rel => {
      degreeMap.set(rel.source, (degreeMap.get(rel.source) || 0) + 1)
      degreeMap.set(rel.target, (degreeMap.get(rel.target) || 0) + 1)
    })
    
    const degrees = Array.from(degreeMap.values())
    if (degrees.length > 0) {
      maxDegree.value = Math.max(...degrees)
    }
  }
}, { immediate: true, deep: true })

const handleSearch = () => {
  emitFilterChange()
}

const handleTypeFilter = () => {
  emitFilterChange()
}

const handleDegreeFilter = () => {
  emitFilterChange()
}

const emitFilterChange = () => {
  const normalizedTypes = selectedTypes.value.map(t => t.toLowerCase())
  emit('filter-change', {
    searchText: searchText.value,
    selectedTypes: normalizedTypes,
    minDegree: minDegree.value
  })
}

const handleReset = () => {
  searchText.value = ''
  selectedTypes.value = []
  minDegree.value = 0
  emitFilterChange()
}
</script>

<style scoped>
.graph-filters-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.graph-filters-card :deep(.el-card__body) {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.filters-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 500;
}

.filters-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-item label {
  font-size: 13px;
  font-weight: 500;
  color: #606266;
}

.el-checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.slider-info {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>


