import axios from 'axios'

// 使用相对路径，适配多端口环境
const API_BASE = ''

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000
})

// 分日数据
export const getDailyData = (params) => api.get('/api/daily', { params })

// 分日数据明细
export const getDailyDetail = (params) => api.get('/api/daily/detail', { params })

// 分期次数据（扁平格式）
export const getCampFlat = (params) => api.get('/api/camp/flat', { params })

// 分期次数据（按品类聚合）
export const getCampByCategory = (params) => api.get('/api/camp/by_category', { params })

// 分期次数据（原始）
export const getCampData = (params) => api.get('/api/camp', { params })

// 趋势数据
export const getTrendData = (params) => api.get('/api/trend', { params })

// 渠道列表
export const getChannels = () => api.get('/api/channels')

// h5id列表
export const getH5ids = (params) => api.get('/api/h5ids', { params })

// AI总结
export const getSummary = (params) => api.get('/api/summary', { params })

// 健康检查
export const healthCheck = () => api.get('/health')

// ============ 刷新配置 API ============

export const getRefreshConfig = () => api.get('/api/refresh/config')
export const saveRefreshConfig = (data) => api.post('/api/refresh/config', data)
export const triggerRefresh = (channels) => api.post('/api/refresh/trigger', { channels })
export const getRefreshStatus = () => api.get('/api/refresh/status')
export const getRefreshLogs = (params) => api.get('/api/refresh/logs', { params })

export default api
