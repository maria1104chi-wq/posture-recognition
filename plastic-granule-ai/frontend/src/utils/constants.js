/**
 * 行为类型常量定义
 */
export const BEHAVIOR_TYPES = {
  NORMAL: '正常',
  SEDENTARY: '久坐',
  SLEEP: '睡眠',
  POWER_ON: '开机动作',
  PULL_PLASTIC: '抽拉塑料长条',
  CHECK_GRANULES: '检查塑料颗粒',
  WEIGH_PACK: '称重打包',
  POWER_OFF: '停机动作',
  CLEAN_MACHINE_HEAD: '清理机头',
  CLEAN_VACUUM: '检查清理真空设备',
}

/**
 * 告警级别定义
 */
export const ALERT_LEVELS = {
  INFO: 'info',
  WARNING: 'warning',
  CRITICAL: 'critical',
}

/**
 * 获取行为对应的标签类型 (Element Plus)
 */
export function getBehaviorTagType(behavior) {
  const typeMap = {
    [BEHAVIOR_TYPES.NORMAL]: 'info',
    [BEHAVIOR_TYPES.SEDENTARY]: 'warning',
    [BEHAVIOR_TYPES.SLEEP]: 'danger',
    [BEHAVIOR_TYPES.POWER_ON]: 'success',
    [BEHAVIOR_TYPES.PULL_PLASTIC]: 'success',
    [BEHAVIOR_TYPES.CHECK_GRANULES]: 'success',
    [BEHAVIOR_TYPES.WEIGH_PACK]: 'success',
    [BEHAVIOR_TYPES.POWER_OFF]: 'info',
    [BEHAVIOR_TYPES.CLEAN_MACHINE_HEAD]: 'success',
    [BEHAVIOR_TYPES.CLEAN_VACUUM]: 'success',
  }
  return typeMap[behavior] || 'info'
}

/**
 * 获取告警级别对应的图标
 */
export function getAlertIcon(level) {
  const iconMap = {
    [ALERT_LEVELS.INFO]: 'InfoFilled',
    [ALERT_LEVELS.WARNING]: 'Warning',
    [ALERT_LEVELS.CRITICAL]: 'Error',
  }
  return iconMap[level] || 'InfoFilled'
}

/**
 * 格式化时间戳
 */
export function formatTimestamp(timestamp) {
  const date = new Date(timestamp * 1000)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
