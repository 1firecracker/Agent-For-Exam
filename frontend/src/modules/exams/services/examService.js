/**
 * 试卷管理 API 服务
 * 对应后端: backend/app/api/exams.py
 */
import { api } from '../../../services/api'

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

        return await api.post(`${API_BASE}/upload`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            onUploadProgress: (progressEvent) => {
                if (onProgress && progressEvent.total) {
                    const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
                    onProgress(percent)
                }
            }
        })
    },

    /**
     * 获取试卷列表
     * @param {Object} params - { year, subject }
     */
    async getExamList(params = {}) {
        return await api.get(API_BASE, { params })
    },

    /**
     * 获取试卷处理状态
     * @param {string} examId 
     */
    async getExamStatus(examId) {
        return await api.get(`${API_BASE}/${examId}/status`)
    },

    /**
     * 获取试卷详情（含结构化题目）
     * @param {string} examId 
     */
    async getExamDetail(examId) {
        return await api.get(`${API_BASE}/${examId}`)
    },

    /**
     * 获取题目抽取前的 raw.md 原始文本
     * @param {string} examId 
     */
    async getExamRaw(examId) {
        return await api.get(`${API_BASE}/${examId}/raw`)
    },

    /**
     * 删除试卷
     * @param {string} examId 
     */
    async deleteExam(examId) {
        return await api.delete(`${API_BASE}/${examId}`)
    },

    /**
     * 重新解析试卷（跳过 OCR）
     * @param {string} examId 
     */
    async reparseExam(examId) {
        return await api.post(`${API_BASE}/${examId}/reparse`)
    },

    /** 更新试卷年份（解析后用户可编辑） */
    async updateExamYear(examId, year) {
        return await api.patch(`${API_BASE}/${examId}/year`, { year })
    }
}

export default examService
