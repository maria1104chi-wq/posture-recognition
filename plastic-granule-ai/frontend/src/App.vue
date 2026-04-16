<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="header-content">
        <h1>🏭 塑料造粒工厂智能监控系统</h1>
        <div class="header-info">
          <el-tag :type="systemStatus === 'running' ? 'success' : 'danger'">
            {{ systemStatus === 'running' ? '系统运行中' : '系统离线' }}
          </el-tag>
          <span class="time">{{ currentTime }}</span>
        </div>
      </div>
    </el-header>
    
    <el-main class="app-main">
      <!-- 摄像头网格 -->
      <div class="camera-grid">
        <div v-for="camera in cameras" :key="camera.id" class="camera-card">
          <el-card :body-style="{ padding: '0px' }" class="camera-card-inner">
            <template #header>
              <div class="card-header">
                <span class="camera-name">
                  <el-icon><VideoCamera /></el-icon>
                  {{ camera.name }} (生产线{{ camera.line_number }})
                </span>
                <div class="card-actions">
                  <el-tag size="small" :type="getBehaviorTypeTag(camera.currentBehavior)">
                    {{ camera.currentBehavior || '正常' }}
                  </el-tag>
                  <el-button size="small" @click="takeSnapshot(camera.id)">
                    <el-icon><Camera /></el-icon>
                  </el-button>
                </div>
              </div>
            </template>
            
            <div class="video-container" @click="connectWebSocket(camera.id)">
              <img 
                v-if="camera.frame" 
                :src="camera.frame" 
                class="video-frame"
                alt="视频流"
              />
              <div v-else class="no-signal">
                <el-icon class="no-signal-icon"><VideoPlay /></el-icon>
                <p>点击连接视频流</p>
              </div>
              
              <!-- 检测结果显示 -->
              <div class="detection-overlay" v-if="camera.detections.length > 0">
                <div v-for="det in camera.detections" :key="det.track_id || det.class_id" 
                     class="detection-label">
                  {{ det.class_name }}: {{ (det.confidence * 100).toFixed(0) }}%
                </div>
              </div>
            </div>
            
            <div class="card-footer">
              <div class="status-info">
                <span>FPS: {{ camera.fps?.toFixed(1) || '0.0' }}</span>
                <span v-if="camera.activePersons > 0">
                  人员：{{ camera.activePersons }}
                </span>
              </div>
              <el-button 
                size="small" 
                :type="camera.connected ? 'success' : 'primary'"
                @click="toggleConnection(camera)"
              >
                {{ camera.connected ? '断开' : '连接' }}
              </el-button>
            </div>
          </el-card>
        </div>
      </div>
      
      <!-- 告警面板 -->
      <div class="alert-panel">
        <el-card>
          <template #header>
            <div class="panel-header">
              <span><el-icon><Warning /></el-icon> 实时告警</span>
              <el-button size="small" @click="loadAlerts">
                <el-icon><Refresh /></el-icon>
              </el-button>
            </div>
          </template>
          
          <el-timeline>
            <el-timeline-item 
              v-for="alert in alerts" 
              :key="alert.timestamp"
              :type="alert.level"
              :timestamp="alert.formatted_time"
              placement="top"
            >
              <el-card>
                <h4>{{ alert.camera_name }} - {{ alert.behavior }}</h4>
                <p>{{ alert.description }}</p>
                <p v-if="alert.capture_path" class="capture-path">
                  抓图：{{ alert.capture_path }}
                </p>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          
          <div v-if="alerts.length === 0" class="no-alerts">
            <el-empty description="暂无告警" :image-size="80" />
          </div>
        </el-card>
      </div>
    </el-main>
  </el-container>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage } from 'element-plus'

// 系统状态
const systemStatus = ref('running')
const currentTime = ref('')
const cameras = ref([])
const alerts = ref([])
const wsConnections = {}

// 更新时间
const updateTime = () => {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN')
}

// 初始化摄像头列表
const initCameras = async () => {
  try {
    const response = await fetch('/api/cameras')
    const data = await response.json()
    
    cameras.value = data.cameras.map(cam => ({
      ...cam,
      frame: null,
      detections: [],
      alerts: [],
      connected: false,
      currentBehavior: '正常',
      activePersons: 0,
      fps: 0
    }))
  } catch (error) {
    console.error('获取摄像头列表失败:', error)
    ElMessage.error('获取摄像头列表失败')
  }
}

// 连接WebSocket
const connectWebSocket = (cameraId) => {
  if (wsConnections[cameraId]) {
    return
  }
  
  const wsUrl = `ws://${window.location.host}/ws/${cameraId}`
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
        camera.fps = 20 // WebSocket推送频率
        
        // 更新检测结果
        camera.detections = data.detections || []
        
        // 更新行为状态
        if (data.detections && data.detections.length > 0) {
          const personDet = data.detections.find(d => d.class_name === 'person')
          if (personDet) {
            // 根据附近物体判断行为
            camera.currentBehavior = inferBehavior(data.detections)
          }
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
      console.error('解析WebSocket消息失败:', error)
    }
  }
  
  ws.onclose = () => {
    console.log(`WebSocket ${cameraId} disconnected`)
    const camera = cameras.value.find(c => c.id === cameraId)
    if (camera) {
      camera.connected = false
    }
    delete wsConnections[cameraId]
  }
  
  ws.onerror = (error) => {
    console.error(`WebSocket ${cameraId} error:`, error)
    ws.close()
  }
  
  wsConnections[cameraId] = ws
}

// 推断行为
const inferBehavior = (detections) => {
  const classNames = detections.map(d => d.class_name)
  
  if (classNames.includes('plastic_strip')) return '抽拉塑料长条'
  if (classNames.includes('granules')) return '检查塑料颗粒'
  if (classNames.includes('scale')) return '称重打包'
  if (classNames.includes('tool')) return '清理作业'
  
  return '正常'
}

// 切换连接
const toggleConnection = (camera) => {
  if (camera.connected) {
    if (wsConnections[camera.id]) {
      wsConnections[camera.id].close()
      delete wsConnections[camera.id]
    }
    camera.connected = false
    camera.frame = null
  } else {
    connectWebSocket(camera.id)
  }
}

// 抓拍
const takeSnapshot = async (cameraId) => {
  try {
    const response = await fetch(`/api/snapshot/${cameraId}`, {
      method: 'POST'
    })
    const data = await response.json()
    ElMessage.success(`抓拍成功：${data.capture_path}`)
  } catch (error) {
    ElMessage.error('抓拍失败')
  }
}

// 加载告警
const loadAlerts = async () => {
  try {
    const response = await fetch('/api/alerts?limit=20')
    const data = await response.json()
    alerts.value = data.alerts
  } catch (error) {
    console.error('加载告警失败:', error)
  }
}

// 获取行为标签类型
const getBehaviorTypeTag = (behavior) => {
  const types = {
    '正常': 'info',
    '久坐': 'warning',
    '睡眠': 'danger',
    '开机动作': 'success',
    '停机动作': 'info',
  }
  return types[behavior] || 'info'
}

// 生命周期
onMounted(() => {
  updateTime()
  setInterval(updateTime, 1000)
  initCameras()
  loadAlerts()
})

onUnmounted(() => {
  // 关闭所有WebSocket连接
  Object.values(wsConnections).forEach(ws => ws.close())
})
</script>

<style scoped>
.app-container {
  height: 100vh;
  background-color: #f5f7fa;
}

.app-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 0 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
}

.header-content h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.time {
  font-size: 14px;
  opacity: 0.9;
}

.app-main {
  padding: 20px;
  overflow-y: auto;
}

.camera-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.camera-card {
  min-width: 0;
}

.camera-card-inner {
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.camera-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.video-container {
  position: relative;
  width: 100%;
  height: 300px;
  background-color: #000;
  cursor: pointer;
  overflow: hidden;
}

.video-frame {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.no-signal {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: #666;
}

.no-signal-icon {
  font-size: 48px;
  margin-bottom: 10px;
}

.detection-overlay {
  position: absolute;
  bottom: 10px;
  left: 10px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.detection-label {
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  background-color: #fafafa;
}

.status-info {
  display: flex;
  gap: 15px;
  font-size: 12px;
  color: #666;
}

.alert-panel {
  max-width: 800px;
  margin: 0 auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.no-alerts {
  padding: 20px 0;
}

.capture-path {
  font-size: 12px;
  color: #999;
  margin-top: 5px;
}
</style>
