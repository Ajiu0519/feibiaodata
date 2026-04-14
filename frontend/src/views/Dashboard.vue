<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElCard, ElRow, ElCol, ElStatistic, ElButton, ElCheckboxGroup, ElCheckbox, ElTimePicker, ElMessage, ElTag, ElDialog, ElSelect, ElOption } from 'element-plus'
import { Money, Document, Plus, Connection } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { getDailyData, getTrendData, getRefreshConfig, saveRefreshConfig, triggerRefresh, getRefreshStatus, getRefreshLogs } from '../api'
import dayjs from 'dayjs'

// 注册 ECharts 组件
use([CanvasRenderer, LineChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const loading = ref(true)
const kpiData = ref({
  todayPay: 0,
  yesterdayPay: 0,
  todayEffective: 0,
  yesterdayEffective: 0,
  todayAddWx: 0,
  yesterdayAddWx: 0
})

// 7天趋势弹窗
const showTrendDialog = ref(false)
const trendDialogTitle = ref('')
const trendLoading = ref(false)
const trendChartData = ref([])
const trendMetric = ref('')
const trendChartRef = ref(null)

// 刷新配置
const refreshConfig = ref({
  all_channels: [],
  enabled_channels: [],
  schedule_time: '08:00'
})
const configLoading = ref(false)

// 预约刷新时间
const schedule10 = ref(false)
const schedule17 = ref(false)
const scheduleCustom = ref(false)
const customTime = ref('')

// 刷新日志
const refreshStatus = ref({ is_running: false })
const refreshLogs = ref([])
const logTotal = ref(0)
const logTimer = ref(null)

// 渠道选择弹窗
const showChannelDialog = ref(false)
const selectedChannels = ref([])

// 趋势数据
const trend7Data = ref([])

// 趋势筛选（Dashboard用）
const trendChannelFilter = ref('')
const trendDaysFilter = ref(7)

// 当前日期格式化
const getCurrentDate = () => dayjs().format('YYYY-MM-DD')
const getToday = () => dayjs().format('YYYY-MM-DD')
const getYesterday = () => dayjs().subtract(1, 'day').format('YYYY-MM-DD')

// 获取当前时间（YYYY-MM-DD HH:mm:ss 格式），用于同一时间段环比
const getCurrentDateTime = () => dayjs().format('YYYY-MM-DD HH:mm:ss')
const getYesterdaySameTime = () => dayjs().subtract(1, 'day').format('YYYY-MM-DD HH:mm:ss')

const calcSum = (data, field) => {
  if (!data || !data.data) return 0
  return data.data.reduce((sum, item) => sum + (Number(item[field]) || 0), 0)
}

const loadKPI = async () => {
  try {
    const now = getCurrentDateTime()
    const yesterdaySameTime = getYesterdaySameTime()
    const today = getToday()
    const yesterday = getYesterday()
    
    // 同一时间段环比：今日从00:00到当前，，昨日从00:00到昨日同一时刻
    const [todayRes, yesterdayRes] = await Promise.all([
      getDailyData({ start_date: today, end_time: now, limit: 1000 }),
      getDailyData({ start_date: yesterday, end_time: yesterdaySameTime, limit: 1000 })
    ])
    
    kpiData.value.todayPay = calcSum(todayRes.data, '支付成功例子数')
    kpiData.value.yesterdayPay = calcSum(yesterdayRes.data, '支付成功例子数')
    kpiData.value.todayEffective = calcSum(todayRes.data, '有效例子数')
    kpiData.value.yesterdayEffective = calcSum(yesterdayRes.data, '有效例子数')
    kpiData.value.todayAddWx = calcSum(todayRes.data, '加微例子数')
    kpiData.value.yesterdayAddWx = calcSum(yesterdayRes.data, '加微例子数')
    
    loading.value = false
  } catch (error) {
    console.error('获取数据失败:', error)
    loading.value = false
  }
}

const loadTrend7Data = async () => {
  try {
    const params = { days: trendDaysFilter.value }
    if (trendChannelFilter.value) {
      params.channel = trendChannelFilter.value
    }
    const res = await getTrendData(params)
    trend7Data.value = res.data.data || []
  } catch (error) {
    console.error('获取趋势数据失败:', error)
  }
}

const loadRefreshConfig = async () => {
  try {
    const res = await getRefreshConfig()
    refreshConfig.value = res.data
    selectedChannels.value = [...res.data.enabled_channels]
    // 解析预约时间
    const times = res.data.schedule_time ? res.data.schedule_time.split(',') : []
    schedule10.value = times.includes('10:00')
    schedule17.value = times.includes('17:00')
  } catch (error) {
    console.error('获取刷新配置失败:', error)
  }
}

const loadRefreshStatus = async () => {
  try {
    const res = await getRefreshStatus()
    refreshStatus.value = res.data
    if (res.data.is_running && !logTimer.value) {
      startLogPolling()
    }
    if (!res.data.is_running && logTimer.value) {
      stopLogPolling()
    }
  } catch (error) {
    console.error('获取刷新状态失败:', error)
  }
}

const startLogPolling = () => {
  logTotal.value = 0
  refreshLogs.value = []
  const poll = async () => {
    try {
      const res = await getRefreshLogs({ since: logTotal.value })
      if (res.data.logs.length > 0) {
        refreshLogs.value = [...refreshLogs.value, ...res.data.logs]
        logTotal.value = res.data.total
      }
      if (res.data.done) {
        stopLogPolling()
      }
    } catch (e) {
      console.error('获取日志失败', e)
    }
  }
  logTimer.value = setInterval(poll, 2000)
}

const stopLogPolling = () => {
  if (logTimer.value) {
    clearInterval(logTimer.value)
    logTimer.value = null
  }
}

const saveConfig = async () => {
  configLoading.value = true
  try {
    await saveRefreshConfig({
      enabled_channels: refreshConfig.value.enabled_channels,
      schedule_time: refreshConfig.value.schedule_time
    })
    ElMessage.success('配置已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    configLoading.value = false
  }
}

const saveScheduleTime = async () => {
  const times = []
  if (schedule10.value) times.push('10:00')
  if (schedule17.value) times.push('17:00')

  if (times.length === 0 && !scheduleCustom.value) {
    ElMessage.warning('请至少选择一个预约时间')
    return
  }

  if (scheduleCustom.value && !customTime.value) {
    ElMessage.warning('请选择自定义时间')
    return
  }

  configLoading.value = true
  try {
    let schedule_time = times.join(',')
    let isOneTime = false

    if (scheduleCustom.value && customTime.value) {
      schedule_time = customTime.value
      isOneTime = true
    }

    await saveRefreshConfig({
      enabled_channels: refreshConfig.value.enabled_channels,
      schedule_time: schedule_time,
      is_one_time: isOneTime
    })
    refreshConfig.value.schedule_time = schedule_time

    if (isOneTime) {
      ElMessage.success(`已预约一次性刷新，时间: ${customTime.value}`)
    } else {
      ElMessage.success('预约时间已保存')
    }
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    configLoading.value = false
  }
}

const openChannelDialog = () => {
  selectedChannels.value = [...refreshConfig.value.enabled_channels]
  showChannelDialog.value = true
}

const confirmChannelSelection = async () => {
  refreshConfig.value.enabled_channels = [...selectedChannels.value]
  showChannelDialog.value = false
  await saveConfig()
  await startRefreshWithChannels(selectedChannels.value)
}

const startRefreshWithChannels = async (channels) => {
  if (!channels || channels.length === 0) {
    ElMessage.warning('请先选择要刷新的渠道')
    return
  }
  refreshLogs.value = []
  logTotal.value = 0
  try {
    const res = await triggerRefresh(channels)
    ElMessage.success(res.data.message || '已开始刷新')
    await loadRefreshStatus()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '启动刷新失败')
  }
}

const getChange = (today, yesterday) => {
  if (!yesterday || yesterday === 0) return 0
  return ((today - yesterday) / yesterday * 100).toFixed(1)
}

// 趋势筛选
const trendChannel = ref('')
const trendDays = ref(7)

const trendOption = computed(() => {
  const data = trendChartData.value
  if (!data || data.length === 0) return {}
  
  const metricMap = {
    pay: { field: 'pay_count', name: '支付成功数' },
    effective: { field: 'effective_count', name: '有效例子数' },
    addwx: { field: 'addwx_count', name: '加微例子数' }
  }
  const metricInfo = metricMap[trendMetric.value] || { field: 'pay_count', name: '支付成功数' }
  
  // 汇总所有渠道数据（按日期聚合）
  const dateSum = {}
  data.forEach(item => {
    const date = item.date
    if (!dateSum[date]) dateSum[date] = 0
    dateSum[date] += Number(item[metricInfo.field]) || 0
  })
  
  const dates = Object.keys(dateSum).sort()
  const totals = dates.map(d => dateSum[d])
  
  return {
    title: { text: `${metricInfo.name} 近${trendDays.value}天汇总`, left: 'center' },
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: { type: 'value' },
    series: [{
      name: '汇总',
      type: 'line',
      smooth: true,
      data: totals,
      areaStyle: { opacity: 0.2 },
      lineStyle: { width: 3 },
      itemStyle: { color: '#409eff' }
    }]
  }
})

// 点击KPI卡片查看7天趋势（汇总）
const openTrendDialog = async (metric, title) => {
  trendMetric.value = metric
  trendDialogTitle.value = title
  showTrendDialog.value = true
  trendLoading.value = true
  trendChartData.value = []
  
  try {
    const res = await getTrendData({ days: trendDays.value })
    trendChartData.value = res.data.data || []
  } catch (error) {
    console.error('获取趋势数据失败:', error)
  } finally {
    // 延迟关闭loading并触发图表resize，确保弹窗渲染完成
    setTimeout(() => {
      trendLoading.value = false
      if (trendChartRef.value) {
        trendChartRef.value.resize()
      }
    }, 200)
  }
}

// 计算趋势图
const buildTrendOption = (data, metric) => {
  const metricMap = {
    pay: { field: 'pay_count', name: '支付成功数' },
    effective: { field: 'effective_count', name: '有效例子数' },
    addwx: { field: 'addwx_count', name: '加微例子数' }
  }
  const metricInfo = metricMap[metric] || { field: 'pay_count', name: '支付成功数' }
  
  const dateMap = {}
  data.forEach(item => {
    if (!dateMap[item.date]) dateMap[item.date] = {}
    dateMap[item.date][item.channel] = Number(item[metricInfo.field]) || 0
  })
  
  const dates = Object.keys(dateMap).sort()
  const channelSet = new Set()
  data.forEach(item => channelSet.add(item.channel))
  const channelList = Array.from(channelSet)
  
  const series = channelList.map(ch => ({
    name: ch, type: 'line', smooth: true,
    data: dates.map(d => dateMap[d][ch] || 0)
  }))
  
  return {
    title: { text: metricInfo.name, left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { data: channelList, bottom: 0, type: 'scroll' },
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: { type: 'value' },
    series
  }
}

const payTrendOption = computed(() => buildTrendOption(trend7Data.value, 'pay'))
const effectiveTrendOption = computed(() => buildTrendOption(trend7Data.value, 'effective'))
const addWxTrendOption = computed(() => buildTrendOption(trend7Data.value, 'addwx'))

const channelCompareOption = computed(() => {
  const data = trend7Data.value
  const channelSum = {}
  data.forEach(item => {
    if (!channelSum[item.channel]) {
      channelSum[item.channel] = { pay: 0, effective: 0, addwx: 0 }
    }
    channelSum[item.channel].pay += Number(item.pay_count) || 0
    channelSum[item.channel].effective += Number(item.effective_count) || 0
    channelSum[item.channel].addwx += Number(item.addwx_count) || 0
  })
  
  const channels = Object.keys(channelSum)
  
  return {
    title: { text: '各渠道汇总对比', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['支付成功', '有效例子', '加微'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    xAxis: { type: 'category', data: channels },
    yAxis: { type: 'value' },
    series: [
      { name: '支付成功', type: 'bar', data: channels.map(c => channelSum[c].pay) },
      { name: '有效例子', type: 'bar', data: channels.map(c => channelSum[c].effective) },
      { name: '加微', type: 'bar', data: channels.map(c => channelSum[c].addwx) }
    ]
  }
})

onMounted(async () => {
  await Promise.all([loadKPI(), loadTrend7Data(), loadRefreshConfig(), loadRefreshStatus()])
})

onUnmounted(() => {
  stopLogPolling()
})
</script>

<template>
  <div class="dashboard">
    <!-- KPI 卡片 -->
    <el-row :gutter="20" class="kpi-row">
      <el-col :span="12">
        <el-card class="kpi-card" shadow="hover" @click="openTrendDialog('effective', '有效例子数')">
          <el-statistic :title="getCurrentDate() + ' 有效例子数'" :value="kpiData.todayEffective">
            <template #prefix><span class="kpi-icon">📋</span></template>
          </el-statistic>
          <div class="kpi-change" :class="getChange(kpiData.todayEffective, kpiData.yesterdayEffective) >= 0 ? 'up' : 'down'">
            环比 {{ getChange(kpiData.todayEffective, kpiData.yesterdayEffective) }}%
          </div>
          <div class="kpi-hint">点击查看7天趋势</div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="kpi-card" shadow="hover" @click="openTrendDialog('addwx', '加微例子数')">
          <el-statistic :title="getCurrentDate() + ' 加微例子数'" :value="kpiData.todayAddWx">
            <template #prefix><span class="kpi-icon">➕</span></template>
          </el-statistic>
          <div class="kpi-change" :class="getChange(kpiData.todayAddWx, kpiData.yesterdayAddWx) >= 0 ? 'up' : 'down'">
            环比 {{ getChange(kpiData.todayAddWx, kpiData.yesterdayAddWx) }}%
          </div>
          <div class="kpi-hint">点击查看7天趋势</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 趋势图表 -->
    <el-card style="margin-top: 20px" v-loading="loading">
      <template #header>
        <span>📈 数据趋势</span>
      </template>
      
      <!-- 趋势筛选工具栏 -->
      <div style="margin-bottom: 16px; display: flex; gap: 12px; align-items: center;">
        <el-select v-model="trendChannelFilter" placeholder="全部渠道" clearable style="width: 150px" @change="loadTrend7Data">
          <el-option v-for="ch in refreshConfig.all_channels" :key="ch" :label="ch" :value="ch" />
        </el-select>
        <el-select v-model="trendDaysFilter" style="width: 120px" @change="loadTrend7Data">
          <el-option :value="7" label="近7天" />
          <el-option :value="14" label="近14天" />
          <el-option :value="30" label="近30天" />
        </el-select>
      </div>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="chart-title">💰 支付成功数趋势</div>
          <v-chart :option="payTrendOption" style="height: 300px" />
        </el-col>
        <el-col :span="12">
          <div class="chart-title">📋 有效例子数趋势</div>
          <v-chart :option="effectiveTrendOption" style="height: 300px" />
        </el-col>
      </el-row>
      
      <el-row :gutter="20" style="margin-top: 20px">
        <el-col :span="12">
          <div class="chart-title">➕ 加微例子数趋势</div>
          <v-chart :option="addWxTrendOption" style="height: 300px" />
        </el-col>
        <el-col :span="12">
          <div class="chart-title">📊 各渠道汇总对比</div>
          <v-chart :option="channelCompareOption" style="height: 300px" />
        </el-col>
      </el-row>
    </el-card>

    <!-- 刷新配置 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>⚙️ 数据刷新配置</span>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <h4>渠道状态</h4>
          <div style="margin-bottom: 12px">
            <el-tag
              v-for="ch in refreshConfig.all_channels"
              :key="ch"
              :type="refreshConfig.enabled_channels.includes(ch) ? 'success' : 'info'"
              :disable-transitions="true"
              style="margin-right: 8px; margin-bottom: 8px"
            >
              {{ ch }}
            </el-tag>
          </div>
          <el-button type="primary" @click="openChannelDialog">
            📡 选择渠道并刷新
          </el-button>
        </el-col>
        
        <el-col :span="12">
          <h4>预约刷新时间</h4>
          <div style="margin-bottom: 12px">
            <el-checkbox v-model="schedule10" label="10:00" style="margin-right: 16px" />
            <el-checkbox v-model="schedule17" label="17:00" style="margin-right: 16px" />
            <el-checkbox v-model="scheduleCustom" label="自定义" />
            <el-time-picker
              v-if="scheduleCustom"
              v-model="customTime"
              format="HH:mm"
              value-format="HH:mm"
              placeholder="选择时间"
              style="margin-left: 8px; width: 100px"
            />
          </div>
          <p style="color: #909399; font-size: 12px; margin-top: 8px">
            当前设置: 每天 10:00 和 17:00 自动刷新
          </p>
          <el-button type="success" @click="saveScheduleTime" :loading="configLoading" style="margin-top: 12px">
            💾 保存定时设置
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 刷新日志 -->
    <el-card style="margin-top: 20px" v-if="refreshLogs.length > 0 || refreshStatus.is_running">
      <template #header>
        <span>
          🔄 刷新日志
          <el-tag v-if="refreshStatus.is_running" type="warning" size="small" style="margin-left: 8px">运行中</el-tag>
          <el-tag v-else type="success" size="small" style="margin-left: 8px">已完成</el-tag>
        </span>
      </template>
      
      <div style="background: #1e1e1e; padding: 16px; border-radius: 8px; font-family: 'Monaco', 'Menlo', monospace; font-size: 13px; line-height: 1.8; max-height: 400px; overflow-y: auto">
        <div 
          v-for="(log, idx) in refreshLogs" 
          :key="idx" 
          style="color: #d4d4d4; white-space: pre-wrap; word-break: break-all"
        >
          <span v-if="log.includes('✅')" style="color: #67c23a">{{ log }}</span>
          <span v-else-if="log.includes('❌')" style="color: #f56c6c">{{ log }}</span>
          <span v-else-if="log.includes('⏭️')" style="color: #909399">{{ log }}</span>
          <span v-else-if="log.includes('>>>')" style="color: #e6a23c; font-weight: bold">{{ log }}</span>
          <span v-else-if="log.includes('    └──')" style="color: #409eff">{{ log }}</span>
          <span v-else-if="log.includes('===')" style="color: #fff; font-weight: bold">{{ log }}</span>
          <span v-else style="color: #d4d4d4">{{ log }}</span>
        </div>
        <div v-if="refreshStatus.is_running" style="color: #ffd700">
          ⏳ 等待更多输出...
        </div>
      </div>
    </el-card>

    <!-- 渠道选择弹窗 -->
    <el-dialog v-model="showChannelDialog" title="选择要刷新的渠道" width="500px">
      <el-checkbox-group v-model="selectedChannels">
        <el-checkbox 
          v-for="ch in refreshConfig.all_channels" 
          :key="ch" 
          :value="ch"
          style="display: block; margin-bottom: 12px"
        >
          {{ ch }}
        </el-checkbox>
      </el-checkbox-group>
      
      <template #footer>
        <el-button @click="showChannelDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmChannelSelection" :disabled="selectedChannels.length === 0">
          开始刷新 ({{ selectedChannels.length }} 个渠道)
        </el-button>
      </template>
    </el-dialog>

    <!-- 趋势弹窗 -->
    <el-dialog v-model="showTrendDialog" :title="trendDialogTitle + ' 近' + trendDays + '天汇总'" width="900px">
      <div style="margin-bottom: 16px; display: flex; gap: 16px; align-items: center;">
        <el-select v-model="trendDays" style="width: 120px" @change="openTrendDialog(trendMetric, trendDialogTitle)">
          <el-option :value="7" label="近7天" />
          <el-option :value="14" label="近14天" />
          <el-option :value="30" label="近30天" />
        </el-select>
      </div>
      <div style="width: 100%; height: 400px;">
        <v-chart ref="trendChartRef" :option="trendOption" :autoresize="true" style="width: 100%; height: 100%;" v-loading="trendLoading" />
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 1400px;
  margin: 0 auto;
}

.kpi-card {
  cursor: pointer;
  transition: transform 0.2s;
}

.kpi-card:hover {
  transform: translateY(-4px);
}

.kpi-change {
  text-align: center;
  font-size: 14px;
  margin-top: 8px;
  padding: 4px 8px;
  border-radius: 4px;
}

.kpi-icon {
  font-size: 20px;
  display: inline-block;
}

.kpi-change.up {
  color: #67c23a;
  background: #f0f9eb;
}

.kpi-change.down {
  color: #f56c6c;
  background: #fef0f0;
}

.kpi-sub {
  text-align: center;
  font-size: 14px;
  margin-top: 8px;
  color: #909399;
}

.kpi-hint {
  text-align: center;
  font-size: 12px;
  margin-top: 8px;
  color: #409eff;
}

.chart-title {
  text-align: center;
  font-size: 14px;
  font-weight: bold;
  margin-bottom: 10px;
  color: #303133;
}

h4 {
  margin: 0 0 12px 0;
  color: #303133;
}
</style>