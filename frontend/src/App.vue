<script setup>
import { ref } from 'vue'
import { ElMenu, ElMenuItem, ElContainer, ElHeader, ElMain, ElCard } from 'element-plus'
import Dashboard from './views/Dashboard.vue'
import DailyTable from './views/DailyTable.vue'
import CampTable from './views/CampTable.vue'
import TrendChart from './views/TrendChart.vue'

const activeMenu = ref('dashboard')

const currentView = ref('Dashboard')

const handleMenuSelect = (index) => {
  activeMenu.value = index
  currentView.value = index.charAt(0).toUpperCase() + index.slice(1)
}
</script>

<template>
  <el-container class="layout-container">
    <el-header class="header">
      <div class="logo">📊 数据可视化平台</div>
      <el-menu 
        mode="horizontal" 
        :default-active="activeMenu"
        @select="handleMenuSelect"
        class="nav-menu"
      >
        <el-menu-item index="dashboard">数据总览</el-menu-item>
        <el-menu-item index="dailyTable">分日数据</el-menu-item>
        <el-menu-item index="campTable">分期次数据</el-menu-item>
        <el-menu-item index="trendChart">数据趋势</el-menu-item>
      </el-menu>
    </el-header>
    <el-main class="main-content">
      <Dashboard v-if="currentView === 'Dashboard'" @navigate="handleMenuSelect" />
      <DailyTable v-else-if="currentView === 'DailyTable'" />
      <CampTable v-else-if="currentView === 'CampTable'" />
      <TrendChart v-else-if="currentView === 'TrendChart'" />
    </el-main>
  </el-container>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.layout-container {
  min-height: 100vh;
  background: #f5f7fa;
}

.header {
  display: flex;
  align-items: center;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 20px;
}

.logo {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin-right: 40px;
}

.nav-menu {
  border-bottom: none;
}

.main-content {
  padding: 20px;
}
</style>
