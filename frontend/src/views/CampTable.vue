<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElTable, ElTableColumn, ElSelect, ElOption, ElButton, ElCard, ElTag, ElRow, ElCheckboxGroup, ElCheckbox, ElDatePicker, ElPagination } from 'element-plus'
import { getCampFlat, getChannels } from '../api'
import dayjs from 'dayjs'

const loading = ref(false)
const channels = ref([])
const tableData = ref([])
const total = ref(0)

// 筛选
const filters = ref({
  categories: ['太极', '八段锦'],
  channel: '',
  dateRange: []
})

// 排序状态：按点击顺序存储排序列 { field, order }
const sortStack = ref([])

// 分页
const pagination = ref({
  current: 1,
  pageSize: 50
})

// 品类选项
const categoryOptions = ['太极', '八段锦']

// 排序字段映射（用于发送给后端）
const sortFieldMap = {
  category: 'category',
  channel: 'channel',
  period: 'period_date',
  pay_count: 'pay_count',
  effective_count: 'effective_count',
  form_rate: 'form_rate',
  d0_arrive_rate: 'd0_arrive_rate',
  d1_arrive_rate: 'd1_arrive_rate',
  zhengjia_rate: 'zhengjia_rate'
}

// 处理表头点击排序
const handleHeaderClick = (field, event) => {
  // 阻止 Element Plus 内置排序
  event.stopPropagation()
  
  const isShift = event.shiftKey
  
  if (isShift) {
    // Shift+点击：添加到排序堆栈
    const existingIndex = sortStack.value.findIndex(s => s.field === field)
    if (existingIndex >= 0) {
      // 已存在，切换顺序
      const existing = sortStack.value[existingIndex]
      sortStack.value.splice(existingIndex, 1, { field, order: existing.order === 'asc' ? 'desc' : 'asc' })
    } else {
      // 新增
      sortStack.value.push({ field, order: 'desc' })
    }
  } else {
    // 普通点击：替换为单列排序
    const existingIndex = sortStack.value.findIndex(s => s.field === field)
    if (existingIndex >= 0) {
      // 已存在，切换顺序
      sortStack.value = [{ field, order: sortStack.value[existingIndex].order === 'asc' ? 'desc' : 'asc' }]
    } else {
      sortStack.value = [{ field, order: 'desc' }]
    }
  }
  
  pagination.value.current = 1
  loadData()
}

// 清除排序
const clearSort = () => {
  sortStack.value = []
  pagination.value.current = 1
  loadData()
}

const loadChannels = async () => {
  try {
    // 近60天有数据的渠道
    const params = {
      start_date: dayjs().subtract(60, 'day').format('YYYY-MM-DD'),
      end_date: dayjs().format('YYYY-MM-DD')
    }
    const res = await getCampFlat(params)
    const allData = res.data.data || []
    // 提取唯一渠道并排序
    const uniqueChannels = [...new Set(allData.map(item => item.channel).filter(c => c))]
    channels.value = uniqueChannels.sort()
  } catch (error) {
    console.error('加载渠道失败:', error)
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {}
    
    if (filters.value.channel) {
      params.channel = filters.value.channel
    }
    
    // 日期范围（近12天）
    if (filters.value.dateRange && filters.value.dateRange.length === 2) {
      params.start_date = filters.value.dateRange[0]
      params.end_date = filters.value.dateRange[1]
    } else {
      // 默认近12天
      params.end_date = dayjs().format('YYYY-MM-DD')
      params.start_date = dayjs().subtract(12, 'day').format('YYYY-MM-DD')
    }
    
    // 排序参数（最多支持3个排序字段）
    if (sortStack.value.length > 0) {
      params.sort_by = sortFieldMap[sortStack.value[0].field] || sortStack.value[0].field
      params.sort_order = sortStack.value[0].order
    }
    if (sortStack.value.length > 1) {
      params.sort_by_2 = sortFieldMap[sortStack.value[1].field] || sortStack.value[1].field
      params.sort_order_2 = sortStack.value[1].order
    }
    if (sortStack.value.length > 2) {
      params.sort_by_3 = sortFieldMap[sortStack.value[2].field] || sortStack.value[2].field
      params.sort_order_3 = sortStack.value[2].order
    }
    
    const res = await getCampFlat(params)
    
    // 前端再过滤品类
    let data = res.data.data || []
    if (filters.value.categories.length > 0 && filters.value.categories.length < 2) {
      data = data.filter(item => item.category === filters.value.categories[0])
    }
    
    tableData.value = data
    total.value = data.length
    
    loading.value = false
  } catch (error) {
    console.error('加载数据失败:', error)
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.value.current = 1
  loadData()
}

const handleReset = () => {
  filters.value = {
    categories: ['太极', '八段锦'],
    channel: '',
    dateRange: []
  }
  sortStack.value = []
  pagination.value.current = 1
  loadData()
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
  return tableData.value.slice(start, start + pagination.value.pageSize)
}

const getRateColor = (rate) => {
  if (!rate || rate === '-' || rate === '0%') return 'info'
  const num = parseFloat(rate)
  if (num >= 50) return 'success'
  if (num >= 30) return 'warning'
  return 'danger'
}

const formatPeriod = (period) => {
  if (!period || period.length !== 6) return period
  return `${period}期`
}

const getSequence = (index) => {
  return (pagination.value.current - 1) * pagination.value.pageSize + index + 1
}

// 判断某字段是否在排序堆栈中
const getSortIndex = (field) => {
  return sortStack.value.findIndex(s => s.field === field)
}

// 获取排序顺序图标
const getSortIcon = (field) => {
  const idx = getSortIndex(field)
  if (idx < 0) return ''
  const order = sortStack.value[idx].order
  const prefix = idx > 0 ? `${idx + 1}.` : ''
  return `${prefix}${order === 'asc' ? '↑' : '↓'}`
}

onMounted(async () => {
  await loadChannels()
  await loadData()
})
</script>

<template>
  <div class="camp-table">
    <el-card>
      <template #header>
        <span>🏕️ 分期次数据</span>
      </template>
      
      <!-- 筛选 -->
      <el-form :inline="true" class="filters">
        <el-form-item label="品类">
          <el-checkbox-group v-model="filters.categories" @change="handleSearch">
            <el-checkbox label="太极" />
            <el-checkbox label="八段锦" />
          </el-checkbox-group>
        </el-form-item>
        
        <el-form-item label="渠道">
          <el-select v-model="filters.channel" placeholder="全部渠道" clearable style="width: 150px" @change="handleSearch">
            <el-option
              v-for="ch in channels"
              :key="ch"
              :label="ch"
              :value="ch"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="期次时间">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 240px"
            @change="handleSearch"
          />
        </el-form-item>
        
        <el-form-item>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
        
        <el-form-item v-if="sortStack.length > 0">
          <el-button size="small" @click="clearSort">清除排序</el-button>
        </el-form-item>
      </el-form>
      
      <!-- 排序提示 -->
      <div v-if="sortStack.length > 0" class="sort-hint">
        <span>当前排序：</span>
        <el-tag v-for="(s, idx) in sortStack" :key="s.field" size="small" style="margin-right: 4px">
          {{ idx + 1 }}. {{ s.field }} {{ s.order === 'asc' ? '↑' : '↓' }}
        </el-tag>
        <span class="hint-text">（按住 Shift 点击表头添加多字段排序）</span>
      </div>
      
      <!-- 数据表格 -->
      <el-table 
        :data="paginatedData()" 
        stripe 
        border
        v-loading="loading"
        style="width: 100%"
        size="small"
      >
        <el-table-column type="index" label="序号" width="60" fixed />
        
        <el-table-column prop="category" label="品类" width="100">
          <template #header>
            <span class="sortable-header" @click="(e) => handleHeaderClick('category', e)">
              品类 {{ getSortIcon('category') }}
            </span>
          </template>
          <template #default="{ row }">
            <el-tag :type="row.category === '太极' ? 'success' : 'warning'" size="small">
              {{ row.category }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="channel" label="渠道" width="120">
          <template #header>
            <span class="sortable-header" @click="(e) => handleHeaderClick('channel', e)">
              渠道 {{ getSortIcon('channel') }}
            </span>
          </template>
        </el-table-column>
        
        <el-table-column prop="period" label="期次" width="110">
          <template #header>
            <span class="sortable-header" @click="(e) => handleHeaderClick('period', e)">
              期次 {{ getSortIcon('period') }}
            </span>
          </template>
          <template #default="{ row }">
            <el-tag type="info">{{ formatPeriod(row.period) }}</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="camp_name" label="训练营名称" min-width="350" show-overflow-tooltip>
          <template #header>
            <span class="sortable-header" @click="(e) => handleHeaderClick('camp_name', e)">
              训练营名称 {{ getSortIcon('camp_name') }}
            </span>
          </template>
        </el-table-column>
        
        <el-table-column prop="pay_count" label="支付成功例子数" width="120">
          <template #header>
            <span class="sortable-header" @click="(e) => handleHeaderClick('pay_count', e)">
              支付成功例子数 {{ getSortIcon('pay_count') }}
            </span>
          </template>
        </el-table-column>
        
        <el-table-column prop="effective_count" label="有效例子数" width="110">
          <template #header>
            <span class="sortable-header" @click="(e) => handleHeaderClick('effective_count', e)">
              有效例子数 {{ getSortIcon('effective_count') }}
            </span>
          </template>
        </el-table-column>
        
        <el-table-column prop="form_rate" label="问卷率" width="90">
          <template #header>
            <span class="sortable-header" @click="(e) => handleHeaderClick('form_rate', e)">
              问卷率 {{ getSortIcon('form_rate') }}
            </span>
          </template>
          <template #default="{ row }">
            <el-tag :type="getRateColor(row.form_rate)" size="small">
              {{ row.form_rate }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="d0_arrive_rate" label="导学课到课率" width="120">
          <template #header>
            <span class="sortable-header" @click="(e) => handleHeaderClick('d0_arrive_rate', e)">
              导学课到课率 {{ getSortIcon('d0_arrive_rate') }}
            </span>
          </template>
          <template #default="{ row }">
            <el-tag :type="getRateColor(row.d0_arrive_rate)" size="small">
              {{ row.d0_arrive_rate }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="d1_arrive_rate" label="D1到课率" width="100">
          <template #header>
            <span class="sortable-header" @click="(e) => handleHeaderClick('d1_arrive_rate', e)">
              D1到课率 {{ getSortIcon('d1_arrive_rate') }}
            </span>
          </template>
          <template #default="{ row }">
            <el-tag :type="getRateColor(row.d1_arrive_rate)" size="small">
              {{ row.d1_arrive_rate }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="zhengjia_rate" label="正价课转化率" width="110">
          <template #header>
            <span class="sortable-header" @click="(e) => handleHeaderClick('zhengjia_rate', e)">
              正价课转化率 {{ getSortIcon('zhengjia_rate') }}
            </span>
          </template>
          <template #default="{ row }">
            <el-tag :type="getRateColor(row.zhengjia_rate)" size="small">
              {{ row.zhengjia_rate }}
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
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next"
          @size-change="handlePageSizeChange"
          @current-change="handlePageChange"
        />
      </el-row>
      
      <el-alert
        type="info"
        :closable="false"
        style="margin-top: 12px"
      >
        <template #title>
          💡 渠道筛选仅显示近60天有数据的渠道 | 默认显示近12天数据，可通过筛选条件调整
        </template>
      </el-alert>
    </el-card>
  </div>
</template>

<style scoped>
.camp-table {
  max-width: 1600px;
  margin: 0 auto;
}

.filters {
  margin-bottom: 12px;
}

.sort-hint {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #ecf5ff;
  border-radius: 4px;
  font-size: 13px;
  color: #409eff;
}

.sort-hint .hint-text {
  color: #909399;
  font-size: 12px;
  margin-left: 8px;
}

.sortable-header {
  cursor: pointer;
  user-select: none;
}

.sortable-header:hover {
  color: #409eff;
}
</style>
