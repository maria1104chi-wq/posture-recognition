<template>
  <el-card>
    <template #header>
      <div class="panel-header">
        <span><el-icon><Warning /></el-icon> 实时告警</span>
        <el-button size="small" @click="$emit('refresh')">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </template>
    
    <el-timeline v-if="alerts.length > 0">
      <el-timeline-item 
        v-for="alert in alerts" 
        :key="alert.timestamp"
        :type="alert.level"
        :timestamp="alert.formatted_time"
        placement="top"
      >
        <el-card class="alert-card">
          <h4>{{ alert.camera_name }} - {{ alert.behavior }}</h4>
          <p>{{ alert.description }}</p>
          <div class="alert-meta">
            <el-tag size="small" :type="getAlertTagType(alert.level)">
              {{ getAlertLevelText(alert.level) }}
            </el-tag>
            <span class="alert-line">生产线 {{ alert.line_number }}</span>
          </div>
        </el-card>
      </el-timeline-item>
    </el-timeline>
    
    <div v-else class="no-alerts">
      <el-empty description="暂无告警" :image-size="80" />
    </div>
  </el-card>
</template>

<script setup>
import { getAlertIcon } from '../utils/constants'

defineProps({
  alerts: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['refresh'])

// 获取告警级别文本
function getAlertLevelText(level) {
  const textMap = {
    info: '提示',
    warning: '警告',
    critical: '严重',
  }
  return textMap[level] || '提示'
}

// 获取告警标签类型
function getAlertTagType(level) {
  const typeMap = {
    info: 'info',
    warning: 'warning',
    critical: 'danger',
  }
  return typeMap[level] || 'info'
}
</script>

<style scoped>
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.alert-card h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
  color: #303133;
}

.alert-card p {
  margin: 0 0 8px 0;
  color: #606266;
  font-size: 14px;
}

.alert-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.alert-line {
  font-size: 12px;
  color: #909399;
}

.no-alerts {
  padding: 20px 0;
}
</style>
