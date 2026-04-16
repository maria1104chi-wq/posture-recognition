<template>
  <div class="home-page">
    <!-- 摄像头网格 -->
    <div class="camera-grid">
      <CameraCard
        v-for="camera in cameras"
        :key="camera.id"
        :camera="camera"
        @connect="handleConnect"
        @disconnect="handleDisconnect"
        @update="loadCameras"
      />
    </div>
    
    <!-- 告警面板 -->
    <div class="alert-panel">
      <AlertPanel 
        :alerts="alerts" 
        @refresh="loadAlerts" 
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import CameraCard from '../components/CameraCard.vue'
import AlertPanel from '../components/AlertPanel.vue'
import apiClient from '../utils/api'

const cameras = ref([])
const alerts = ref([])
const wsConnections = {}

// 加载摄像头列表
async function loadCameras() {
  try {
    const data = await apiClient.get('/cameras')
    cameras.value = (data.cameras || []).map(cam => ({
      ...cam,
      frame: null,
      detections: [],
      connected: false,
      currentBehavior: '正常',
      activePersons: 0,
    }))
  } catch (error) {
    console.error('获取摄像头列表失败:', error)
    ElMessage.error('获取摄像头列表失败')
  }
}

// 加载告警记录
async function loadAlerts() {
  try {
    const data = await apiClient.get('/alerts?limit=20')
    alerts.value = data.alerts || []
  } catch (error) {
    console.error('加载告警失败:', error)
  }
}

// 连接 WebSocket
function handleConnect(cameraId) {
  if (wsConnections[cameraId]) {
    return
  }
  
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws/${cameraId}`
  const ws = new WebSocket(wsUrl)
  
  ws.onopen = () => {
    console.log(`WebSocket ${cameraId} connected`)
    const camera = cameras.value.find(c => c.id === cameraId)
    if (camera) {
      camera.connected = true
    }
  }
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      const camera = cameras.value.find(c => c.id === data.camera_id)
      
      if (camera) {
        // 更新视频帧
        camera.frame = `data:image/jpeg;base64,${data.frame}`
        camera.fps = 20
        
        // 更新检测结果
        camera.detections = data.detections || []
        
        // 更新行为状态
        if (data.detections && data.detections.length > 0) {
          camera.currentBehavior = inferBehavior(data.detections)
          camera.activePersons = data.detections.filter(d => d.class_name === 'person').length
        }
        
        // 处理告警
        if (data.alerts && data.alerts.length > 0) {
          data.alerts.forEach(alert => {
            alerts.value.unshift(alert)
            if (alerts.value.length > 50) {
              alerts.value.pop()
            }
          })
          
          // 显示告警通知
          const latestAlert = data.alerts[data.alerts.length - 1]
          ElMessage.warning({
            message: `${latestAlert.camera_name}: ${latestAlert.description}`,
            duration: 5000
          })
        }
      }
    } catch (error) {
      console.error('解析 WebSocket 消息失败:', error)
    }
  }
  
  ws.onclose = () => {
    console.log(`WebSocket ${cameraId} disconnected`)
    const camera = cameras.value.find(c => c.id === cameraId)
    if (camera) {
      camera.connected = false
      camera.frame = null
    }
    delete wsConnections[cameraId]
  }
  
  ws.onerror = (error) => {
    console.error(`WebSocket ${cameraId} error:`, error)
    ws.close()
  }
  
  wsConnections[cameraId] = ws
}

// 断开 WebSocket
function handleDisconnect(cameraId) {
  if (wsConnections[cameraId]) {
    wsConnections[cameraId].close()
    delete wsConnections[cameraId]
  }
}

// 推断行为
function inferBehavior(detections) {
  const classNames = detections.map(d => d.class_name)
  
  if (classNames.includes('plastic_strip')) return '抽拉塑料长条'
  if (classNames.includes('granules')) return '检查塑料颗粒'
  if (classNames.includes('scale')) return '称重打包'
  if (classNames.includes('tool')) return '清理作业'
  
  return '正常'
}

// 生命周期
onMounted(() => {
  loadCameras()
  loadAlerts()
})

onUnmounted(() => {
  // 关闭所有 WebSocket 连接
  Object.values(wsConnections).forEach(ws => ws.close())
})
</script>

<style scoped>
.home-page {
  padding: 20px;
}

.camera-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.alert-panel {
  max-width: 800px;
  margin: 0 auto;
}
</style>
