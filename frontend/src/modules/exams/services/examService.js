/**
 * 试卷管理 API 服务
 * 对应后端: backend/app/api/exams.py
 */
import axios from 'axios'

const API_BASE = '/api/exams'

const examService = {
    /**
     * 上传试卷 PDF
     * @param {File} file - PDF 文件
     * @param {Object} options - 可选参数 { year, title, subject }
     * @param {Function} onProgress - 上传进度回调
     */
    async uploadExam(file, options = {}, onProgress = null) {
        const formData = new FormData()
        formData.append('file', file)

        if (options.year) formData.append('year', options.year)
        if (options.title) formData.append('title', options.title)
        if (options.subject) formData.append('subject', options.subject)

        const response = await axios.post(`${API_BASE}/upload`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            onUploadProgress: (progressEvent) => {
                if (onProgress && progressEvent.total) {
                    const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
                    onProgress(percent)
                }
            }
        })
        return response.data
    },

    /**
     * 获取试卷列表
     * @param {Object} params - { year, subject }
     */
    async getExamList(params = {}) {
        const response = await axios.get(API_BASE, { params })
        return response.data
    },

    /**
     * 获取试卷处理状态
     * @param {string} examId 
     */
    async getExamStatus(examId) {
        const response = await axios.get(`${API_BASE}/${examId}/status`)
        return response.data
    },

    /**
     * 获取试卷详情（含结构化题目）
     * @param {string} examId 
     */
    async getExamDetail(examId) {
        const response = await axios.get(`${API_BASE}/${examId}`)
        return response.data
    },

    /**
     * 删除试卷
     * @param {string} examId 
     */
    async deleteExam(examId) {
        const response = await axios.delete(`${API_BASE}/${examId}`)
        return response.data
    },

    /**
     * 重新解析试卷（跳过 OCR）
     * @param {string} examId 
     */
    async reparseExam(examId) {
        const response = await axios.post(`${API_BASE}/${examId}/reparse`)
        return response.data
    }
}

export default examService
