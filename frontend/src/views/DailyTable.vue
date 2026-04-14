<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElTable, ElTableColumn, ElSelect, ElDatePicker, ElButton, ElCard, ElPagination, ElTag, ElRow } from 'element-plus'
import { getDailyData, getDailyDetail, getChannels } from '../api'
import dayjs from 'dayjs'

const loading = ref(false)
const channels = ref([])
const total = ref(0)

// 缓存管理
const CACHE_KEY = 'daily_data_cache'
const CACHE_EXPIRE = 5 * 60 * 1000 // 5分钟过期

const getCache = () => {
  try {
    const cached = localStorage.getItem(CACHE_KEY)
    if (cached) {
      const { data, timestamp } = JSON.parse(cached)
      if (Date.now() - timestamp < CACHE_EXPIRE) {
        return data
      }
    }
  } catch (e) {}
  return null
}

const setCache = (data) => {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({
      data,
      timestamp: Date.now()
    }))
  } catch (e) {}
}

const clearCache = () => {
  localStorage.removeItem(CACHE_KEY)
}

// 缓存的数据
const cachedData = ref([])

// 筛选条件
const filters = ref({
  channel: [],
  dateRange: [dayjs().subtract(6, 'day').format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')]
})

// 分页
const pagination = ref({
  current: 1,
  pageSize: 20
})

// 聚合数据
const aggregatedData = ref([])
// 展开状态
const expandedKeys = ref(new Set())

// H5ID 明细缓存
const detailCache = ref({})

// 获取排序后的明细数据
const getSortedDetailData = (key) => {
  const data = detailCache.value[key] || []
  // 默认按有效例子数降序排序
  return [...data].sort((a, b) => {
    const aVal = parseInt(a['有效例子数']) || 0
    const bVal = parseInt(b['有效例子数']) || 0
    return bVal - aVal
  })
}

// 快速日期选择
const quickDateOptions = [
  { label: '今日', value: 'today' },
  { label: '昨日', value: 'yesterday' },
  { label: '近7天', value: '7' },
  { label: '近14天', value: '14' },
  { label: '近30天', value: '30' }
]
const selectedQuickDate = ref('7')

const setQuickDateRange = (type) => {
  selectedQuickDate.value = type
  const today = dayjs()

  if (type === 'today') {
    filters.value.dateRange = [today.format('YYYY-MM-DD'), today.format('YYYY-MM-DD')]
  } else if (type === 'yesterday') {
    const yesterday = today.subtract(1, 'day')
    filters.value.dateRange = [yesterday.format('YYYY-MM-DD'), yesterday.format('YYYY-MM-DD')]
  } else {
    const days = parseInt(type)
    filters.value.dateRange = [today.subtract(days - 1, 'day').format('YYYY-MM-DD'), today.format('YYYY-MM-DD')]
  }
}

const loadChannels = async () => {
  try {
    // 使用与后端配置一致的渠道列表
    channels.value = ['星视点', '江苏数赢', '中正运动', '元创', '弘景']
  } catch (error) {
    console.error('加载渠道失败:', error)
  }
}

const buildCacheKey = () => {
  const dateRange = filters.value.dateRange || []
  return `${filters.value.channel?.join(',') || 'all'}|${dateRange[0] || ''}|${dateRange[1] || ''}`
}

const loadData = async (forceRefresh = false) => {
  loading.value = true
  
  const cacheKey = buildCacheKey()
  const cached = getCache()
  
  // 如果有缓存且不是强制刷新，且缓存key匹配，直接用缓存
  if (!forceRefresh && cached && cached.key === cacheKey && cached.aggregatedData) {
    aggregatedData.value = cached.aggregatedData
    total.value = cached.total
    loading.value = false
    return
  }
  
  try {
    const params = {
      limit: 5000,
      aggregate: true
    }
    
    if (filters.value.channel && filters.value.channel.length > 0) {
      params.channel = filters.value.channel.join(',')
    }
    
    if (filters.value.dateRange && filters.value.dateRange.length === 2) {
      params.start_date = filters.value.dateRange[0]
      params.end_date = filters.value.dateRange[1]
    } else {
      // 默认加载最近7天
      params.end_date = dayjs().format('YYYY-MM-DD')
      params.start_date = dayjs().subtract(7, 'day').format('YYYY-MM-DD')
    }
    
    const res = await getDailyData(params)
    aggregatedData.value = res.data.data || []
    total.value = res.data.count || 0
    
    // 保存到缓存
    setCache({
      key: cacheKey,
      aggregatedData: aggregatedData.value,
      total: total.value
    })
    
    loading.value = false
  } catch (error) {
    console.error('加载数据失败:', error)
    loading.value = false
  }
}

const toggleExpand = async (row) => {
  const key = `${row.date}|${row.channel}`
  console.log('toggleExpand called with:', row.date, row.channel, key)
  
  if (expandedKeys.value.has(key)) {
    expandedKeys.value.delete(key)
  } else {
    expandedKeys.value.add(key)
    console.log('expandedKeys after add:', Array.from(expandedKeys.value))
    
    if (!detailCache.value[key]) {
      try {
        console.log('Fetching detail for:', row.date, row.channel)
        const res = await getDailyDetail({ date: row.date, channel: row.channel })
        console.log('Detail API response:', res.data)
        detailCache.value[key] = res.data.data || []
        console.log('detailCache after update:', Object.keys(detailCache.value))
      } catch (e) {
        console.error('加载明细失败:', e)
        detailCache.value[key] = []
      }
    }
  }
  
  expandedKeys.value = new Set(expandedKeys.value)
}

const isExpanded = (row) => {
  return expandedKeys.value.has(`${row.date}|${row.channel}`)
}

const handleSearch = () => {
  pagination.value.current = 1
  expandedKeys.value = new Set()
  detailCache.value = {}
  loadData(true) // 强制刷新
}

const handleReset = () => {
  selectedQuickDate.value = '7'
  filters.value = { channel: [], dateRange: [dayjs().subtract(6, 'day').format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')] }
  pagination.value.current = 1
  expandedKeys.value = new Set()
  detailCache.value = {}
  clearCache()
  loadData(true)
}

const handlePageChange = (page) => {
  pagination.value.current = page
}

const handlePageSizeChange = (size) => {
  pagination.value.pageSize = size
  pagination.value.current = 1
}

const paginatedData = () => {
  const start = (pagination.value.current - 1) * pagination.value.pageSize
  return aggregatedData.value.slice(start, start + pagination.value.pageSize)
}

const getRateColor = (rate) => {
  if (!rate || rate === '-') return ''
  const num = parseFloat(rate)
  if (num >= 50) return 'success'
  if (num >= 30) return 'warning'
  return 'danger'
}

onMounted(async () => {
  await loadChannels()
  await loadData()
})
</script>

<template>
  <div class="daily-table">
    <el-card>
      <template #header>
        <span>📅 分日数据</span>
      </template>
      
      <!-- 筛选条件 -->
      <el-form :inline="true" class="filters">
        <el-form-item label="渠道">
          <el-select v-model="filters.channel" placeholder="全部渠道" multiple clearable style="width: 200px">
            <el-option
              v-for="ch in channels"
              :key="ch"
              :label="ch"
              :value="ch"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="日期范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 240px"
          />
          <div style="margin-top: 8px">
            <el-radio-group v-model="selectedQuickDate" size="small" @change="setQuickDateRange">
              <el-radio-button v-for="opt in quickDateOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </el-radio-button>
            </el-radio-group>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 当前日期范围显示 -->
      <div v-if="filters.dateRange && filters.dateRange.length === 2" style="margin-bottom: 12px; color: #606266; font-size: 14px">
        当前筛选：{{ filters.dateRange[0] }} 至 {{ filters.dateRange[1] }} (共 {{ dayjs(filters.dateRange[1]).diff(dayjs(filters.dateRange[0]), 'day') + 1 }} 天)
      </div>
      
      <!-- 每页条数 -->
      <el-row style="margin-bottom: 12px" justify="end">
        <span style="color: #606266; margin-right: 8px">每页显示:</span>
        <el-select v-model="pagination.pageSize" style="width: 100px" @change="handlePageSizeChange">
          <el-option :value="10" label="10条" />
          <el-option :value="20" label="20条" />
          <el-option :value="50" label="50条" />
        </el-select>
      </el-row>
      
      <!-- 数据表格 -->
      <el-table 
        :data="paginatedData()" 
        stripe 
        border
        v-loading="loading"
        style="width: 100%"
        :row-class-name="() => 'clickable-row'"
        :expand-row-keys="Array.from(expandedKeys)"
        :row-key="(row) => `${row.date}|${row.channel}`"
        @row-click="toggleExpand"
      >
        <el-table-column type="expand" width="50">
          <template #default="{ row: outerRow }">
            <div v-if="isExpanded(outerRow)" style="padding: 12px 48px; background: #fafafa">
              <el-tag type="info" style="margin-bottom: 12px">
                💡 {{ outerRow.channel }} - {{ outerRow.date }} H5ID明细 (只显示支付>0)
              </el-tag>
              <el-table
                :data="getSortedDetailData(`${outerRow.date}|${outerRow.channel}`)"
                size="small"
                border
              >
                <el-table-column prop="h5id" label="H5ID" width="120" sortable />
                <el-table-column prop="支付成功例子数" label="支付成功数" width="120" sortable />
                <el-table-column prop="有效例子数" label="有效例子数" width="120" sortable />
                <el-table-column prop="临时例子数" label="临时例子数" width="100" sortable />
                <el-table-column prop="加微例子数" label="加微例子数" width="100" sortable />
                <el-table-column prop="加微率" label="加微率" width="100" sortable>
                  <template #default="{ row: detailRow }">
                    <el-tag :type="getRateColor(detailRow['加微率'])" size="small">
                      {{ detailRow['加微率'] }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="领课时间" label="领课时间" width="120" />
        <el-table-column prop="渠道" label="渠道" width="150" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="isExpanded(row)" type="success" size="small">已展开</el-tag>
            <el-tag v-else type="info" size="small">点击展开</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="支付成功例子数" label="支付成功数" width="120" />
        <el-table-column prop="有效例子数" label="有效例子数" width="120" />
        <el-table-column prop="临时例子数" label="临时例子数" width="100" />
        <el-table-column prop="加微例子数" label="加微例子数" width="100" />
        <el-table-column prop="加微率" label="加微率" width="100">
          <template #default="{ row }">
            <el-tag :type="getRateColor(row['加微率'])" size="small">
              {{ row['加微率'] }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <el-row style="margin-top: 16px" justify="end">
        <el-pagination
          v-model:current-page="pagination.current"
          :page-size="pagination.pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @Size-change="handlePageSizeChange"
          @current-change="handlePageChange"
        />
      </el-row>
      
      <el-alert
        type="info"
        :closable="false"
        style="margin-top: 12px"
      >
        <template #title>
          💡 数据缓存5分钟，点击"查询"强制刷新 | 共 {{ total }} 条数据
        </template>
      </el-alert>
    </el-card>
  </div>
</template>

<style scoped>
.daily-table {
  max-width: 1400px;
  margin: 0 auto;
}

.filters {
  margin-bottom: 16px;
}

:deep(.clickable-row) {
  cursor: pointer;
}

:deep(.clickable-row:hover) {
  background-color: #f5f7fa;
}
</style>
