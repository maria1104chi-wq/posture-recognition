<template>
  <div class="camera-card-wrapper">
    <el-card :body-style="{ padding: '0px' }" class="camera-card-inner">
      <template #header>
        <div class="card-header">
          <span class="camera-name">
            <el-icon><VideoCamera /></el-icon>
            {{ camera.name }} (生产线{{ camera.line_number }})
          </span>
          <div class="card-actions">
            <el-tag size="small" :type="getBehaviorTagType(camera.currentBehavior)">
              {{ camera.currentBehavior || '正常' }}
            </el-tag>
            <el-button size="small" @click="handleSnapshot" :loading="snapshotLoading">
              <el-icon><Camera /></el-icon>
            </el-button>
          </div>
        </div>
      </template>
      
      <div class="video-container" @click="handleConnect">
        <img 
          v-if="camera.frame" 
          :src="camera.frame" 
          class="video-frame"
          alt="视频流"
        />
        <div v-else class="no-signal">
          <el-icon class="no-signal-icon"><VideoPlay /></el-icon>
          <p>{{ camera.connected ? '连接中...' : '点击连接视频流' }}</p>
        </div>
        
        <!-- 检测结果显示 -->
        <div class="detection-overlay" v-if="camera.detections.length > 0">
          <div v-for="det in camera.detections.slice(0, 5)" :key="det.track_id || det.class_id" 
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
          @click.stop="handleConnect"
        >
          {{ camera.connected ? '断开' : '连接' }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getBehaviorTagType } from '../utils/constants'
import apiClient from '../utils/api'

const props = defineProps({
  camera: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['connect', 'disconnect', 'update'])

const snapshotLoading = ref(false)

// 处理连接/断开
const handleConnect = () => {
  if (props.camera.connected) {
    emit('disconnect', props.camera.id)
  } else {
    emit('connect', props.camera.id)
  }
}

// 处理抓拍
const handleSnapshot = async () => {
  try {
    snapshotLoading.value = true
    const data = await apiClient.post(`/snapshot/${props.camera.id}`)
    ElMessage.success(`抓拍成功：${data.capture_path}`)
    emit('update')
  } catch (error) {
    ElMessage.error('抓拍失败')
  } finally {
    snapshotLoading.value = false
  }
}
</script>

<style scoped>
.camera-card-wrapper {
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
</style>
