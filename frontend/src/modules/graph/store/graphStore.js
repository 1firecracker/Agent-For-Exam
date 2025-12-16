import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import graphService from '../services/graphService'

export const useGraphStore = defineStore('graph', () => {
  const entities = ref([])
  const relations = ref([])
  const totalEntities = ref(0)
  const totalRelations = ref(0)
  const loading = ref(false)
  const error = ref(null)
  const queryResult = ref(null)
  const querying = ref(false)

  const hasData = computed(() => {
    return entities.value.length > 0 || relations.value.length > 0
  })

  async function loadGraph(conversationId) {
    loading.value = true
    error.value = null
    try {
      const response = await graphService.getGraph(conversationId)
      entities.value = response.entities || []
      relations.value = response.relations || []
      totalEntities.value = response.total_entities || 0
      totalRelations.value = response.total_relations || 0
      return response
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  async function getEntity(conversationId, entityId) {
    try {
      return await graphService.getEntity(conversationId, entityId)
    } catch (err) {
      error.value = err
      throw err
    }
  }

  async function getRelation(conversationId, source, target) {
    try {
      return await graphService.getRelation(conversationId, source, target)
    } catch (err) {
      error.value = err
      throw err
    }
  }

  async function query(conversationId, queryText, mode = 'naive') {
    querying.value = true
    error.value = null
    queryResult.value = null
    try {
      const response = await graphService.query(conversationId, queryText, mode)
      queryResult.value = response
      return response
    } catch (err) {
      error.value = err
      throw err
    } finally {
      querying.value = false
    }
  }

  async function getGraphStatus(conversationId) {
    try {
      return await graphService.getGraphStatus(conversationId)
    } catch (err) {
      error.value = err
      throw err
    }
  }

  function clearGraph() {
    entities.value = []
    relations.value = []
    totalEntities.value = 0
    totalRelations.value = 0
    queryResult.value = null
  }

  function reset() {
    clearGraph()
    loading.value = false
    querying.value = false
    error.value = null
  }

  return {
    entities,
    relations,
    totalEntities,
    totalRelations,
    loading,
    error,
    queryResult,
    querying,
    hasData,
    loadGraph,
    getEntity,
    getRelation,
    query,
    getGraphStatus,
    clearGraph,
    reset
  }
})


