import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../utils/api'

export const useCameraStore = defineStore('camera', () => {
  // 状态
  const cameras = ref([])
  const alerts = ref([])
  const systemStatus = ref('running')

  // 获取摄像头列表
  async function fetchCameras() {
    try {
      const data = await apiClient.get('/cameras')
      cameras.value = data.cameras || []
      return data.cameras
    } catch (error) {
      console.error('获取摄像头列表失败:', error)
      throw error
    }
  }

  // 获取摄像头状态
  async function fetchCameraStatus(cameraId) {
    try {
      const data = await apiClient.get(`/cameras/${cameraId}/status`)
      return data
    } catch (error) {
      console.error(`获取摄像头${cameraId}状态失败:`, error)
      throw error
    }
  }

  // 获取告警记录
  async function fetchAlerts(limit = 50) {
    try {
      const data = await apiClient.get(`/alerts?limit=${limit}`)
      alerts.value = data.alerts || []
      return data.alerts
    } catch (error) {
      console.error('获取告警记录失败:', error)
      throw error
    }
  }

  // 手动抓拍
  async function takeSnapshot(cameraId) {
    try {
      const data = await apiClient.post(`/snapshot/${cameraId}`)
      return data
    } catch (error) {
      console.error(`抓拍摄像头${cameraId}失败:`, error)
      throw error
    }
  }

  // 添加告警
  function addAlert(alert) {
    alerts.value.unshift(alert)
    if (alerts.value.length > 100) {
      alerts.value.pop()
    }
  }

  // 更新摄像头帧
  function updateCameraFrame(cameraId, frameData) {
    const camera = cameras.value.find(c => c.id === cameraId)
    if (camera) {
      camera.frame = `data:image/jpeg;base64,${frameData.frame}`
      camera.fps = 20
      camera.detections = frameData.detections || []
      camera.activePersons = frameData.detections?.filter(d => d.class_name === 'person').length || 0
    }
  }

  // 设置系统状态
  function setSystemStatus(status) {
    systemStatus.value = status
  }

  return {
    cameras,
    alerts,
    systemStatus,
    fetchCameras,
    fetchCameraStatus,
    fetchAlerts,
    takeSnapshot,
    addAlert,
    updateCameraFrame,
    setSystemStatus,
  }
})
