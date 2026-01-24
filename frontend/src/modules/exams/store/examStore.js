/**
 * 试卷管理 Store (Pinia)
 * 管理试卷上传、列表、状态轮询
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import examService from '../services/examService'

export const useExamStore = defineStore('exam', () => {
    // State
    const exams = ref([])
    const loading = ref(false)
    const uploading = ref(false)
    const uploadProgress = ref(0)
    const error = ref(null)

    // 状态轮询定时器 { examId: timerId }
    const pollingTimers = ref({})

    // Getters
    const getExamsBySubject = computed(() => {
        return (subjectId) => {
            // 目前后端没有按 subject 筛选，先返回全部
            // 后续可以增加 subject 字段筛选
            return exams.value
        }
    })

    const processingExams = computed(() => {
        return exams.value.filter(e => e.status === 'processing' || e.status === 'pending')
    })

    const completedExams = computed(() => {
        return exams.value.filter(e => e.status === 'completed')
    })

    // Actions

    /**
     * 加载试卷列表
     * @param {Object} params - { year, subject }
     */
    async function loadExams(params = {}) {
        loading.value = true
        error.value = null
        try {
            const response = await examService.getExamList(params)
            exams.value = response.items || []

            // 自动开始轮询处理中的试卷
            const processing = exams.value.filter(e => e.status === 'processing' || e.status === 'pending')
            processing.forEach(exam => {
                startPolling(exam.exam_id)
            })

            return response
        } catch (err) {
            error.value = err
            throw err
        } finally {
            loading.value = false
        }
    }

    /**
     * 上传试卷
     * @param {File} file 
     * @param {Object} options - { year, title, subject }
     */
    async function uploadExam(file, options = {}) {
        uploading.value = true
        uploadProgress.value = 0
        error.value = null

        try {
            const response = await examService.uploadExam(
                file,
                options,
                (percent) => { uploadProgress.value = percent }
            )

            uploadProgress.value = 100

            // 添加到列表
            if (response.exam_id) {
                exams.value.unshift({
                    exam_id: response.exam_id,
                    year: response.year,
                    title: response.title || file.name,
                    status: 'processing',
                    created_at: new Date().toISOString()
                })

                // 开始轮询状态
                startPolling(response.exam_id)
            }

            return response
        } catch (err) {
            error.value = err
            uploadProgress.value = 0
            throw err
        } finally {
            uploading.value = false
            setTimeout(() => { uploadProgress.value = 0 }, 500)
        }
    }

    /**
     * 获取试卷状态
     */
    async function getExamStatus(examId) {
        try {
            const status = await examService.getExamStatus(examId)

            // 更新本地列表
            const index = exams.value.findIndex(e => e.exam_id === examId)
            if (index !== -1) {
                exams.value[index] = { ...exams.value[index], ...status }
            }

            return status
        } catch (err) {
            error.value = err
            throw err
        }
    }

    /**
     * 获取试卷详情
     */
    async function getExamDetail(examId) {
        try {
            return await examService.getExamDetail(examId)
        } catch (err) {
            error.value = err
            throw err
        }
    }

    /**
     * 删除试卷
     */
    async function deleteExam(examId) {
        loading.value = true
        try {
            await examService.deleteExam(examId)

            // 从列表移除
            const index = exams.value.findIndex(e => e.exam_id === examId)
            if (index !== -1) {
                exams.value.splice(index, 1)
            }

            // 停止轮询
            stopPolling(examId)
        } catch (err) {
            error.value = err
            throw err
        } finally {
            loading.value = false
        }
    }

    /**
     * 重试解析（跳过 OCR）
     */
    async function reparseExam(examId) {
        try {
            await examService.reparseExam(examId)

            // 更新本地状态为 processing 并开始轮询
            const index = exams.value.findIndex(e => e.exam_id === examId)
            if (index !== -1) {
                exams.value[index].status = 'processing'
            }
            startPolling(examId)
        } catch (err) {
            error.value = err
            throw err
        }
    }

    /**
     * 开始轮询试卷状态
     */
    function startPolling(examId, interval = 3000) {
        if (pollingTimers.value[examId]) return // 已在轮询

        const poll = async () => {
            try {
                const status = await getExamStatus(examId)

                if (status.status === 'completed' || status.status === 'failed') {
                    stopPolling(examId)
                }
            } catch (err) {
                console.error(`Polling exam ${examId} failed:`, err)
            }
        }

        // 立即执行一次
        poll()

        // 定时轮询
        pollingTimers.value[examId] = setInterval(poll, interval)
    }

    /**
     * 停止轮询
     */
    function stopPolling(examId) {
        if (pollingTimers.value[examId]) {
            clearInterval(pollingTimers.value[examId])
            delete pollingTimers.value[examId]
        }
    }

    /**
     * 停止所有轮询
     */
    function stopAllPolling() {
        Object.keys(pollingTimers.value).forEach(id => {
            stopPolling(id)
        })
    }

    /**
     * 重置状态
     */
    function reset() {
        stopAllPolling()
        exams.value = []
        loading.value = false
        uploading.value = false
        uploadProgress.value = 0
        error.value = null
    }

    return {
        // State
        exams,
        loading,
        uploading,
        uploadProgress,
        error,

        // Getters
        getExamsBySubject,
        processingExams,
        completedExams,

        // Actions
        loadExams,
        uploadExam,
        getExamStatus,
        getExamDetail,
        deleteExam,
        reparseExam,
        startPolling,
        stopPolling,
        stopAllPolling,
        reset
    }
})
