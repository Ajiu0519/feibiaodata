<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { ElCard, ElRow, ElCol, ElSelect, ElOption, ElButton, ElDatePicker } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { getTrendData, getChannels } from '../api'
import dayjs from 'dayjs'

// 注册 ECharts 组件
use([CanvasRenderer, LineChart, BarChart, PieChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const loading = ref(false)
const channels = ref([])
const trendData = ref([])

// 筛选条件
const filters = ref({
  channel: '',
  days: 7
})

onMounted(async () => {
  await loadChannels()
  await loadData()
})

const loadChannels = async () => {
  try {
    const res = await getChannels()
    channels.value = res.data.channels.filter(c => c) || []
  } catch (error) {
    console.error('加载渠道失败:', error)
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      days: filters.value.days
    }
    
    if (filters.value.channel) {
      params.channel = filters.value.channel
    }
    
    const res = await getTrendData(params)
    trendData.value = res.data.data || []
  } catch (error) {
    console.error('加载数据失败:', error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  loadData()
}

const handleReset = () => {
  filters.value = {
    channel: '',
    days: 7
  }
  loadData()
}

// 折线图配置
const lineOption = computed(() => {
  const data = trendData.value
  
  // 按日期分组
  const dateMap = {}
  data.forEach(item => {
    if (!dateMap[item.date]) {
      dateMap[item.date] = {}
    }
    dateMap[item.date][item.channel] = {
      pay: item.pay_count,
      effective: item.effective_count,
      addwx: item.addwx_count
    }
  })
  
  const dates = Object.keys(dateMap).sort()
  
  // 获取所有渠道
  const channelSet = new Set()
  data.forEach(item => channelSet.add(item.channel))
  const channelList = Array.from(channelSet)
  
  const series = channelList.map(ch => ({
    name: ch,
    type: 'line',
    smooth: true,
    data: dates.map(d => dateMap[d][ch]?.pay || 0)
  }))
  
  return {
    title: {
      text: '📈 支付成功数趋势'
    },
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: channelList,
      bottom: 0
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false
    },
    yAxis: {
      type: 'value'
    },
    series
  }
})

// 柱状图配置
const barOption = computed(() => {
  const data = trendData.value
  
  // 按渠道汇总
  const channelSum = {}
  data.forEach(item => {
    if (!channelSum[item.channel]) {
      channelSum[item.channel] = { pay: 0, effective: 0, addwx: 0 }
    }
    channelSum[item.channel].pay += item.pay_count || 0
    channelSum[item.channel].effective += item.effective_count || 0
    channelSum[item.channel].addwx += item.addwx_count || 0
  })
  
  const channels = Object.keys(channelSum)
  const payData = channels.map(c => channelSum[c].pay)
  const effectiveData = channels.map(c => channelSum[c].effective)
  
  return {
    title: {
      text: '📊 各渠道汇总对比'
    },
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['支付成功', '有效例子'],
      bottom: 0
    },
    xAxis: {
      type: 'category',
      data: channels
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '支付成功',
        type: 'bar',
        data: payData
      },
      {
        name: '有效例子',
        type: 'bar',
        data: effectiveData
      }
    ]
  }
})

// 饼图配置
const pieOption = computed(() => {
  const data = trendData.value
  
  // 按渠道汇总支付数
  const channelSum = {}
  data.forEach(item => {
    if (!channelSum[item.channel]) {
      channelSum[item.channel] = 0
    }
    channelSum[item.channel] += item.pay_count || 0
  })
  
  const pieData = Object.keys(channelSum).map(ch => ({
    name: ch,
    value: channelSum[ch]
  }))
  
  return {
    title: {
      text: '🥧 渠道占比',
      left: 'center'
    },
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center'
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false,
          position: 'center'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 20,
            fontWeight: 'bold'
          }
        },
        labelLine: {
          show: false
        },
        data: pieData
      }
    ]
  }
})
</script>

<template>
  <div class="trend-chart">
    <el-card>
      <template #header>
        <span>📈 数据趋势</span>
      </template>
      
      <!-- 筛选条件 -->
      <el-form :inline="true" class="filters">
        <el-form-item label="渠道">
          <el-select v-model="filters.channel" placeholder="全部渠道" clearable style="width: 150px">
            <el-option
              v-for="ch in channels"
              :key="ch"
              :label="ch"
              :value="ch"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="天数">
          <el-select v-model="filters.days" style="width: 100px">
            <el-option :value="7" label="近7天" />
            <el-option :value="14" label="近14天" />
            <el-option :value="30" label="近30天" />
          </el-select>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
      
      <!-- 图表 -->
      <el-row :gutter="20" v-loading="loading">
        <el-col :span="24">
          <v-chart :option="lineOption" style="height: 400px" />
        </el-col>
      </el-row>
      
      <el-row :gutter="20" style="margin-top: 20px">
        <el-col :span="12">
          <v-chart :option="barOption" style="height: 350px" />
        </el-col>
        <el-col :span="12">
          <v-chart :option="pieOption" style="height: 350px" />
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<style scoped>
.trend-chart {
  max-width: 1400px;
  margin: 0 auto;
}

.filters {
  margin-bottom: 20px;
}
</style>
