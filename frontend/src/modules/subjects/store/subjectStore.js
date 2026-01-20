import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import subjectService from '../services/subjectService'

export const useSubjectStore = defineStore('subject', () => {
  const subjects = ref([])
  const currentSubjectId = ref(null)
  const loading = ref(false)
  const error = ref(null)

  const currentSubject = computed(() => {
    if (!currentSubjectId.value) return null
    return subjects.value.find(s => s.subject_id === currentSubjectId.value) || null
  })

  async function loadSubjects() {
    loading.value = true
    error.value = null
    try {
      const response = await subjectService.getSubjects()
      subjects.value = response || []
      return response
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  async function createSubject(name = null, description = null) {
    loading.value = true
    error.value = null
    try {
      const subject = await subjectService.createSubject(name, description)
      subjects.value.push(subject)
      currentSubjectId.value = subject.subject_id
      return subject
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  function selectSubject(subjectId) {
    currentSubjectId.value = subjectId
  }

  async function updateSubject(subjectId, name = null, description = null) {
    loading.value = true
    error.value = null
    try {
      const updated = await subjectService.updateSubject(subjectId, name, description)
      const index = subjects.value.findIndex(s => s.subject_id === subjectId)
      if (index !== -1) {
        subjects.value[index] = updated
      }
      return updated
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  async function deleteSubject(subjectId) {
    loading.value = true
    error.value = null
    try {
      await subjectService.deleteSubject(subjectId)
      subjects.value = subjects.value.filter(s => s.subject_id !== subjectId)
      if (currentSubjectId.value === subjectId) {
        currentSubjectId.value = null
      }
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  function reset() {
    subjects.value = []
    currentSubjectId.value = null
    loading.value = false
    error.value = null
  }

  return {
    subjects,
    currentSubjectId,
    loading,
    error,
    currentSubject,
    loadSubjects,
    createSubject,
    selectSubject,
    updateSubject,
    deleteSubject,
    reset
  }
})


