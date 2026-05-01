<template>
  <div class="container mx-auto px-4 py-6">
    <transition name="toast-slide">
      <div v-if="statusMessage" :class="['top-toast', statusType === 'error' ? 'error' : 'success']">
        <i class="fas" :class="statusType === 'error' ? 'fa-circle-exclamation' : 'fa-circle-check'"></i>
        <span>{{ statusMessage }}</span>
      </div>
    </transition>

    <div class="flex justify-between items-center mb-6 flex-wrap gap-3">
      <h1 class="text-2xl font-bold text-gray-800 flex items-center">
        <i class="fas fa-chart-line mr-2 text-blue-500"></i>手术视频分析
      </h1>
      <div class="flex flex-wrap gap-2">
        <button v-if="shouldShowUploadButton" class="btn-primary" @click="triggerVideoUpload">
          <i class="fas fa-upload mr-2"></i>上传视频
        </button>
        <input ref="videoFileInput" class="hidden" type="file" accept="video/*" @change="onVideoSelected" />
        <button class="btn-secondary" @click="exportAnnotations">
          <i class="fas fa-share-alt mr-2"></i>导出标注
        </button>
        <button class="btn-secondary" :class="isTracking ? 'btn-active' : ''" @click="toggleTracking">
          <i class="fas fa-broadcast-tower mr-2"></i>实时追踪: {{ isTracking ? '开' : '关' }}
        </button>
        <button class="btn-ghost" @click="exportSummary">
          <i class="fas fa-download mr-2"></i>导出报告
        </button>
      </div>
    </div>

    <div class="bg-white rounded-lg shadow-md p-6 mb-6">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="lg:col-span-2 space-y-4">
          <div class="video-container h-[600px]" ref="videoContainer">
            <video
              ref="videoEl"
              :src="uploadedVideoUrl"
              class="w-full h-full object-cover"
              controls
              playsinline
              preload="metadata"
              @loadedmetadata="onLoadedMetadata"
              @canplay="setCanvasSize"
              @timeupdate="onTimeUpdate"
              @click.stop.prevent="toggleVideoPlayback"
              v-show="uploadedVideoUrl"
            ></video>
            <img :src="analysisImageSrc" alt="手术视频" class="w-full h-full object-cover" v-show="!uploadedVideoUrl" />
            <canvas ref="maskCanvas" class="mask-canvas"></canvas>
            <div class="points-layer">
              <span
                v-for="(point, idx) in pointsForDisplay"
                :key="idx"
                class="point-dot"
                :class="point.kind === 'positive' ? 'point-positive' : 'point-negative'"
                :style="`left: ${point.x}px; top: ${point.y}px`"
              ></span>
            </div>
          </div>

          <div class="seg-toolbar-external">
            <button class="seg-btn" :class="isAddPositive ? 'seg-btn-active' : ''" @click="setPointMode(true)">
              <i class="fas fa-plus-circle text-green-600 mr-1"></i>正样本
            </button>
            <button class="seg-btn" :class="!isAddPositive ? 'seg-btn-active neg' : ''" @click="setPointMode(false)">
              <i class="fas fa-minus-circle text-red-500 mr-1"></i>负样本
            </button>
            <button class="seg-btn" @click="clearPoints">
              <i class="fas fa-undo mr-1"></i>清点
            </button>
            <button class="seg-btn primary" :disabled="isProcessing" @click="runSegmentation">
              <i class="fas" :class="isProcessing ? 'fa-spinner fa-spin' : 'fa-magic'"></i>
              <span class="ml-2">视频分析</span>
            </button>
          </div>

          <div class="flex flex-wrap items-center gap-3">
            <div class="text-sm text-slate-700 font-semibold flex items-center gap-2">
              <i class="fas fa-clock text-blue-500"></i>
              <span>{{ formatTimeLabel(currentTime) }} / {{ formatTimeLabel(duration) }}</span>
            </div>
            <div class="flex items-center gap-2">
              <label class="text-sm text-slate-600">掩码透明度</label>
              <input type="range" min="0.2" max="0.8" step="0.05" v-model.number="maskOpacity" @input="onOpacityChange" />
            </div>
            <div class="badge" :class="currentMask ? '' : 'ghost'">{{ currentMask ? '已生成分割' : '等待生成' }}</div>
          </div>

          <div class="timeline-shell">
            <div class="timeline-bar">
              <div class="h-full bg-blue-600 progress" :style="{ width: progressPercent }"></div>
              <span
                v-for="note in notesSorted"
                :key="note.id"
                class="note-marker"
                :style="{ left: markerLeft(note.time) }"
                :title="formatTimeLabel(note.time) + ' ' + note.text"
              ></span>
            </div>
            <div class="flex justify-between mt-2 text-sm text-gray-600">
              <span>00:00</span>
              <span>{{ formatTimeLabel(duration || 165) }}</span>
            </div>
          </div>

          <div class="note-panel">
            <div class="note-form">
              <button
                class="annotation-timer"
                :class="isTimingAnnotation ? 'recording' : ''"
                :title="isTimingAnnotation ? '结束计时' : '开始计时'"
                @click="toggleAnnotationTimer"
              >
                <i class="fas" :class="isTimingAnnotation ? 'fa-stop' : 'fa-clock'"></i>
                <span>{{ annotationIntervalLabel }}</span>
              </button>
              <input v-model="noteTimeInput" class="input note-time" placeholder="mm:ss - mm:ss" style="width: 130px;" />
              <input v-model="noteTextInput" class="input note-text" placeholder="输入文字注释内容" style="width: 200px;" />
              <button class="btn-secondary compact" @click="addNote">添加注释</button>
              <button class="btn-secondary compact" @click="clearAnnotationTimer">
                清除计时
              </button>
              <button v-if="activeLoopNoteId" class="btn-secondary compact" @click="exitNoteLoop">
                退出循环
              </button>
            </div>
            <div class="note-list">
              <div v-show="!notesSorted.length" class="note-empty">暂无文字注释</div>
              <div v-show="notesSorted.length">
                <div
                  v-for="note in notesSorted"
                  :key="note.id"
                  class="note-row"
                  :class="activeLoopNoteId === note.id ? 'active-loop' : ''"
                  @click="playNoteLoop(note)"
                >
                  <div>
                    <p class="note-time-label"><i class="fas fa-clock"></i> {{ formatNoteRange(note) }}</p>
                    <p class="note-text">{{ note.text }}</p>
                  </div>
                  <div class="note-actions">
                    <span v-if="activeLoopNoteId === note.id" class="loop-chip">循环播放中</span>
                    <button class="note-delete" @click.stop="removeNote(note.id)"><i class="fas fa-trash"></i></button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="space-y-4">
          <div class="bg-gray-50 p-4 rounded-lg shadow-sm">
            <h3 class="font-semibold text-lg mb-3 flex items-center">
              <i class="fas fa-circle-info mr-2 text-blue-500"></i>基本信息
            </h3>
            <div class="space-y-3">
              <div class="bg-white p-4 rounded-md shadow-sm space-y-3">
                <div class="flex justify-between items-center text-sm">
                  <span class="text-gray-500">项目名称</span>
                  <span class="font-semibold text-slate-800">{{ currentProject?.title || '未命名项目' }}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-gray-500">术式名称</span>
                  <span class="font-semibold text-slate-800">{{ currentProject?.procedure || '未填写' }}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-gray-500">术者</span>
                  <span class="font-semibold text-slate-800">{{ currentProject?.surgeon || '未填写' }}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-gray-500">日期</span>
                  <span class="font-semibold text-slate-800">{{ currentProject?.date || '未填写' }}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-gray-500">视频总时长</span>
                  <span class="font-semibold text-slate-800">{{ formatTimeLabel(duration || 165) }}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-gray-500">状态</span>
                  <span
                    class="text-xs rounded-full px-3 py-1"
                    :class="statusClass(currentProject?.status)"
                  >
                    {{ currentProject?.status || '待分析' }}
                  </span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-gray-500">视频文件</span>
                  <span class="font-semibold text-slate-800 break-all text-right max-w-[65%]">{{ currentProject?.fileName || '未上传' }}</span>
                </div>
              </div>
            </div>

          </div>

          <div class="bg-gray-50 p-4 rounded-lg">
            <h3 class="font-semibold text-lg mb-3 flex items-center">
              <i class="fas fa-chart-pie mr-2 text-blue-500"></i>分析概览
            </h3>
            <div class="grid grid-cols-2 gap-4">
              <div class="bg-white p-3 rounded-md shadow-sm">
                <p class="text-sm text-gray-500">手术时长</p>
                <p class="font-bold">{{ formatTimeLabel(duration || 165) }}</p>
              </div>
              <div class="bg-white p-3 rounded-md shadow-sm">
                <p class="text-sm text-gray-500">标注记录数</p>
                <p class="font-bold">{{ annotations.length }}</p>
              </div>
              <div class="bg-white p-3 rounded-md shadow-sm">
                <p class="text-sm text-gray-500">关键步骤</p>
                <p class="font-bold">{{ generatedSteps.length }}</p>
              </div>
              <div class="bg-white p-3 rounded-md shadow-sm">
                <p class="text-sm text-gray-500">异常检测</p>
                <p class="font-bold" :class="anomalyStatus.toneClass">
                  {{ anomalyStatus.label }}
                </p>
                <p class="text-xs text-slate-400 mt-1">将由独立异常模型提供</p>
              </div>
            </div>
          </div>

          <div class="bg-gray-50 p-4 rounded-lg">
            <h3 class="font-semibold text-lg mb-3 flex items-center">
              <i class="fas fa-chart-bar mr-2 text-blue-500"></i>器械使用频率
            </h3>
            <div class="chart-container">
              <div class="h-full flex items-end space-x-2">
                <div class="w-1/5 bg-blue-500 rounded-t" style="height: 70%;"></div>
                <div class="w-1/5 bg-blue-400 rounded-t" style="height: 40%;"></div>
                <div class="w-1/5 bg-blue-300 rounded-t" style="height: 60%;"></div>
                <div class="w-1/5 bg-blue-200 rounded-t" style="height: 30%;"></div>
                <div class="w-1/5 bg-blue-100 rounded-t" style="height: 20%;"></div>
              </div>
              <div class="flex justify-between mt-2 text-xs text-gray-500">
                <span>抓持钳</span>
                <span>电凝钩</span>
                <span>分离钳</span>
                <span>剪刀</span>
                <span>吸引器</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="bg-white rounded-lg shadow-md p-6">
      <div class="flex justify-between items-center gap-3 mb-4 flex-wrap">
        <h2 class="text-xl font-semibold flex items-center">
          <i class="fas fa-list-ol mr-2 text-blue-500"></i>关键步骤分析
        </h2>
        <div class="flex items-center gap-2 flex-wrap">
          <span v-if="phaseAnalysisResult?.meta" class="text-sm text-slate-500">
            已采样 {{ phaseAnalysisResult.meta.sampleCount }} 帧，设备 {{ phaseAnalysisResult.meta.device }}
          </span>
          <span v-if="phaseAnalysisState?.status" class="text-sm text-slate-500">
            任务状态：{{ phaseStatusLabel }}
          </span>
          <button class="btn-secondary" :disabled="phaseLoading || isPhaseRunning" @click="runPhaseAnalysis">
            <i class="fas" :class="phaseLoading ? 'fa-spinner fa-spin' : 'fa-wand-magic-sparkles'"></i>
            <span class="ml-2">{{ phaseLoading ? '提交中' : isPhaseRunning ? '后台分析进行中' : '开始关键步骤分析' }}</span>
          </button>
        </div>
      </div>

      <div v-if="phaseAnalysisState" class="phase-progress-panel">
        <div class="flex justify-between items-center gap-3 flex-wrap">
          <div>
            <p class="phase-stage">{{ phaseAnalysisState.stageLabel || phaseStatusLabel }}</p>
            <p class="phase-message">{{ phaseAnalysisState.message || '等待关键步骤分析任务更新。' }}</p>
          </div>
          <span class="phase-percent">{{ phaseAnalysisState.progress || 0 }}%</span>
        </div>
        <div class="phase-progress-track">
          <div class="phase-progress-bar" :style="{ width: `${phaseAnalysisState.progress || 0}%` }"></div>
        </div>
      </div>

      <div v-if="!projectVideoFile" class="empty">
        当前项目还没有可分析的视频，请先上传视频后再执行关键步骤分析。
      </div>

      <div v-else-if="phaseError" class="status-box error mb-4">
        {{ phaseError }}
      </div>

      <div v-else-if="isPhaseRunning" class="empty">
        关键步骤分析正在后台运行。你现在可以离开当前页面继续查看其他项目，稍后返回时结果会自动同步并保存到当前项目。
      </div>

      <div v-else-if="!generatedSteps.length" class="empty">
        模型分析结果会在这里展示。点击右上角“开始关键步骤分析”后，将根据当前项目视频生成高置信度阶段时间线。
      </div>

      <div v-else class="space-y-4">
        <div v-for="(step, index) in generatedSteps" :key="step.id" class="flex items-start">
          <div class="bg-blue-100 text-blue-800 rounded-full w-8 h-8 flex items-center justify-center mr-4 flex-shrink-0">{{ index + 1 }}</div>
          <div class="flex-grow">
            <div class="flex items-center gap-3 flex-wrap">
              <h3 class="font-medium">{{ step.title }}</h3>
              <span class="text-xs rounded-full px-2 py-1 bg-slate-100 text-slate-600">
                置信度 {{ formatConfidence(step.confidence) }}
              </span>
            </div>
            <p class="text-sm text-gray-600 mt-1">{{ step.description }}</p>
            <div class="mt-2 flex items-center text-sm flex-wrap gap-x-3 gap-y-1">
              <span class="text-gray-500">{{ step.time }}</span>
              <span :class="step.level === '高置信度' ? 'text-green-600' : 'text-yellow-600'">
                <i :class="step.level === '高置信度' ? 'fas fa-check-circle mr-1' : 'fas fa-exclamation-circle mr-1'"></i>{{ step.level }}
              </span>
            </div>
          </div>
          <button class="ml-4 text-blue-600 hover:text-blue-800" @click="seekTo(step.seconds)"><i class="fas fa-play"></i> 查看</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { createPhaseAnalysisJob, getPhaseAnalysisJob } from '../api/phaseAnalysis'
import { applyPhaseAnalysisToProject, syncProjectPhaseAnalysis } from '../phaseAnalysisStore'
import { getActiveProject, saveProject, setActiveProject } from '../projectStore'
import { getProjectVideo, saveProjectVideo } from '../videoStore'

const videoFileInput = ref(null)
const uploadedVideoUrl = ref('')
const currentProject = ref(null)
const projectVideoFile = ref(null)

const videoEl = ref(null)
const videoContainer = ref(null)
const maskCanvas = ref(null)
const maskCtx = ref(null)

const positivePoints = ref([])
const negativePoints = ref([])
const isAddPositive = ref(true)
const isProcessing = ref(false)
const maskOpacity = ref(0.45)
const currentMask = ref(null)
const annotations = ref([])
const selectedAnnotationId = ref(null)
const annotationName = ref('关键器械')
const annotationType = ref('scalpel')
const statusMessage = ref('')
const statusType = ref('success')

const notes = ref([])
const noteTimeInput = ref('')
const noteTextInput = ref('')
const annotationTimerStart = ref(null)
const annotationTimerEnd = ref(null)
const isTimingAnnotation = ref(false)
const activeLoopNoteId = ref(null)
const activeLoopRange = ref(null)
let statusTimer = null

const currentTime = ref(0)
const duration = ref(165)
const phaseAnalysisResult = ref(null)
const phaseLoading = ref(false)
const phaseError = ref('')
const phaseJobStatus = ref('')
let phasePollingTimer = null

const typeOptions = [
  { value: 'scalpel', label: '电凝钩' },
  { value: 'clamp', label: '抓持钳' },
  { value: 'needle', label: '夹闭夹' },
  { value: 'scissors', label: '剪刀' },
  { value: 'forceps', label: '分离钳' },
  { value: 'other', label: '其他器械' },
]

const colorMap = {
  scalpel: '#ef4444',
  clamp: '#3b82f6',
  needle: '#8b5cf6',
  scissors: '#10b981',
  forceps: '#f59e0b',
  other: '#0ea5e9',
}

const isTracking = ref(false)
const lastTrackTime = ref(0)

const pointsForDisplay = computed(() => [
  ...positivePoints.value.map((p) => ({ ...p, kind: 'positive' })),
  ...negativePoints.value.map((p) => ({ ...p, kind: 'negative' })),
])

const shouldShowUploadButton = computed(() => {
  if (!currentProject.value) return true
  return !currentProject.value.hasVideo && !uploadedVideoUrl.value
})

const progressPercent = computed(() => {
  if (!duration.value) return '0%'
  const ratio = Math.min(1, currentTime.value / duration.value)
  return `${(ratio * 100).toFixed(1)}%`
})

const shouldRequireVideo = computed(() => {
  if (!currentProject.value) return true
  return currentProject.value.status === '草稿' || !projectVideoFile.value || !uploadedVideoUrl.value
})

const notesSorted = computed(() => notes.value.slice().sort((a, b) => a.time - b.time))

const annotationIntervalLabel = computed(() => {
  if (annotationTimerStart.value === null) return '计时'
  if (annotationTimerEnd.value === null) return `${formatTimeLabel(annotationTimerStart.value)} - ...`
  return `${formatTimeLabel(annotationTimerStart.value)} - ${formatTimeLabel(annotationTimerEnd.value)}`
})

const generatedSteps = computed(() => phaseAnalysisResult.value?.steps || [])

const phaseAnalysisState = computed(() => currentProject.value?.phaseAnalysis || null)

const isPhaseRunning = computed(() => ['queued', 'running'].includes(phaseAnalysisState.value?.status))

const phaseStatusLabel = computed(() => {
  const status = phaseAnalysisState.value?.status
  if (status === 'queued') return '排队中'
  if (status === 'running') return '分析中'
  if (status === 'completed') return '分析完成'
  if (status === 'failed') return '分析失败'
  return status || '待分析'
})

const anomalyStatus = computed(() => {
  return { label: '待接入', toneClass: 'text-slate-500' }
})

function triggerVideoUpload() {
  videoFileInput.value?.click()
}

function requireVideoBeforeAction() {
  if (!shouldRequireVideo.value) return false
  showStatus('请先上传视频后再进行操作', 'error')
  return true
}

function persistProjectNotes() {
  if (!currentProject.value) return
  const updatedProject = {
    ...currentProject.value,
    notes: notes.value,
    updatedAt: new Date().toISOString(),
    updatedAtLabel: new Date().toLocaleString('zh-CN'),
  }
  currentProject.value = updatedProject
  saveProject(updatedProject)
  setActiveProject(updatedProject)
}

function revokeUploadedVideoUrl() {
  if (uploadedVideoUrl.value && uploadedVideoUrl.value.startsWith('blob:')) {
    URL.revokeObjectURL(uploadedVideoUrl.value)
    uploadedVideoUrl.value = ''
  }
}

async function onVideoSelected(event) {
  const file = event?.target?.files?.[0]
  if (!file) return

  revokeUploadedVideoUrl()
  uploadedVideoUrl.value = URL.createObjectURL(file)
  projectVideoFile.value = file
  phaseAnalysisResult.value = null
  phaseError.value = ''
  phaseJobStatus.value = ''

  if (currentProject.value) {
    await saveProjectVideo(currentProject.value.id, file)
    const updatedProject = {
      ...currentProject.value,
      fileName: file.name,
      hasVideo: true,
      videoUrl: '',
      status: '待分析',
      phaseAnalysis: null,
      updatedAt: new Date().toISOString(),
      updatedAtLabel: new Date().toLocaleString('zh-CN'),
    }
    currentProject.value = updatedProject
    saveProject(updatedProject)
    setActiveProject(updatedProject)
    showStatus('视频已加载到当前项目，可继续分析', 'success')
  }
}

function onLoadedMetadata() {
  duration.value = videoEl.value?.duration || duration.value
  setCanvasSize()
}

function onTimeUpdate() {
  currentTime.value = videoEl.value?.currentTime || 0
  syncLoopPlayback()
  if (isTracking.value) updateMaskTracking()
}

function syncLoopPlayback() {
  if (!videoEl.value || !activeLoopRange.value) return

  const { startTime, endTime } = activeLoopRange.value
  if (currentTime.value < startTime) {
    videoEl.value.currentTime = startTime
    return
  }

  if (currentTime.value >= endTime) {
    videoEl.value.currentTime = startTime
    videoEl.value.play?.()
  }
}

function updateMaskTracking() {
  if (!currentMask.value || !videoEl.value || videoEl.value.paused) return
  const now = currentTime.value
  let dt = now - lastTrackTime.value
  if (dt <= 0) return
  dt = Math.min(dt, 0.2)

  const velocity = currentMask.value.velocity || { x: 20, y: 8 }
  const dx = velocity.x * dt
  const dy = velocity.y * dt
  const nextPoints = currentMask.value.points.map((pt) => ({ x: pt.x + dx, y: pt.y + dy }))

  currentMask.value = {
    ...currentMask.value,
    points: nextPoints,
    lastCenter: getPolygonCenter(nextPoints),
  }

  drawMask(currentMask.value)
  lastTrackTime.value = now
}

function setCanvasSize() {
  if (!videoContainer.value || !maskCanvas.value) return
  const { clientWidth, clientHeight } = videoContainer.value
  maskCanvas.value.width = clientWidth
  maskCanvas.value.height = clientHeight
  if (!maskCtx.value) maskCtx.value = maskCanvas.value.getContext('2d')
  if (currentMask.value) drawMask(currentMask.value)
}

function markerLeft(time) {
  if (!duration.value) return '0%'
  const ratio = Math.min(1, Math.max(0, time / duration.value))
  return `${(ratio * 100).toFixed(2)}%`
}

function toggleVideoPlayback() {
  if (requireVideoBeforeAction()) return
  if (!videoEl.value) return
  if (videoEl.value.paused) {
    videoEl.value.play?.()
  } else {
    videoEl.value.pause()
  }
}

function toggleAnnotationTimer() {
  if (requireVideoBeforeAction()) return
  const seconds = videoEl.value?.currentTime ?? currentTime.value
  if (!Number.isFinite(seconds)) return

  if (!isTimingAnnotation.value) {
    annotationTimerStart.value = seconds
    annotationTimerEnd.value = null
    isTimingAnnotation.value = true
    noteTimeInput.value = `${formatTimeLabel(seconds)} - ...`
    showStatus('注释开始时间已记录', 'success')
    return
  }

  const start = annotationTimerStart.value ?? seconds
  annotationTimerStart.value = Math.min(start, seconds)
  annotationTimerEnd.value = Math.max(start, seconds)
  isTimingAnnotation.value = false
  noteTimeInput.value = `${formatTimeLabel(annotationTimerStart.value)} - ${formatTimeLabel(annotationTimerEnd.value)}`
  showStatus('注释结束时间已记录，可输入文字内容保存', 'success')
}

function clearAnnotationTimer() {
  if (requireVideoBeforeAction()) return
  annotationTimerStart.value = null
  annotationTimerEnd.value = null
  isTimingAnnotation.value = false
  noteTimeInput.value = ''
}

function setPointMode(isPositive) {
  if (requireVideoBeforeAction()) return
  isAddPositive.value = isPositive
}

function clearPoints() {
  if (requireVideoBeforeAction()) return
  positivePoints.value = []
  negativePoints.value = []
}

function onOpacityChange() {
  if (currentMask.value) {
    currentMask.value.opacity = maskOpacity.value
    drawMask(currentMask.value)
  }
}

async function runSegmentation() {
  if (requireVideoBeforeAction()) return
  if (!positivePoints.value.length) {
    showStatus('请至少添加一个正样本点', 'error')
    return
  }

  isProcessing.value = true
  showStatus('正在生成分析掩码...', 'success')
  await new Promise((resolve) => setTimeout(resolve, 400))

  const color = colorMap[annotationType.value] || '#3b82f6'
  const maskPoints = generateMaskFromPoints(positivePoints.value, negativePoints.value)

  currentMask.value = {
    points: maskPoints,
    color,
    opacity: maskOpacity.value,
    velocity: { x: 20, y: 8 },
    lastCenter: getPolygonCenter(maskPoints),
  }

  drawMask(currentMask.value)
  isTracking.value = true
  lastTrackTime.value = currentTime.value
  isProcessing.value = false
  showStatus('已生成分析区域，可以保存标注', 'success')
}

async function runPhaseAnalysis() {
  if (requireVideoBeforeAction()) return
  if (!projectVideoFile.value) {
    phaseError.value = '当前项目没有可分析的视频文件。'
    return
  }

  phaseLoading.value = true
  phaseError.value = ''
  showStatus('已提交关键步骤分析任务，后台会继续处理。', 'success')

  try {
    const job = await createPhaseAnalysisJob(projectVideoFile.value, { sampleSeconds: 2 })
    phaseJobStatus.value = job.status

    if (currentProject.value) {
      const updatedProject = applyPhaseAnalysisToProject(currentProject.value, job)
      currentProject.value = updatedProject
      saveProject(updatedProject)
      setActiveProject(updatedProject)
    }

    startPhasePolling()
  } catch (error) {
    phaseError.value = error?.message || '关键步骤分析失败，请检查后端服务是否启动。'
    showStatus(phaseError.value, 'error')
  } finally {
    phaseLoading.value = false
  }
}

function stopPhasePolling() {
  if (phasePollingTimer) {
    window.clearInterval(phasePollingTimer)
    phasePollingTimer = null
  }
}

function startPhasePolling() {
  stopPhasePolling()
  phasePollingTimer = window.setInterval(async () => {
    await refreshPhaseJob()
  }, 4000)
}

async function refreshPhaseJob() {
  const jobId = currentProject.value?.phaseAnalysis?.jobId
  const status = currentProject.value?.phaseAnalysis?.status
  if (!jobId || !['queued', 'running'].includes(status)) {
    stopPhasePolling()
    return
  }

  try {
    const job = await getPhaseAnalysisJob(jobId)
    phaseJobStatus.value = job.status
    const updatedProject = applyPhaseAnalysisToProject(currentProject.value, job)
    currentProject.value = updatedProject
    phaseAnalysisResult.value = job.result || null
    phaseError.value = job.error || ''
    saveProject(updatedProject)
    setActiveProject(updatedProject)

    if (job.status === 'completed') {
      stopPhasePolling()
      showStatus(`关键步骤分析完成，保留 ${job.result?.steps?.length || 0} 个高置信度步骤`, 'success')
    } else if (job.status === 'failed') {
      stopPhasePolling()
      showStatus(job.error || '关键步骤分析失败', 'error')
    }
  } catch (error) {
    phaseError.value = error?.message || '关键步骤分析状态获取失败'
  }
}

function drawMask(mask) {
  if (!maskCtx.value || !maskCanvas.value) return
  maskCtx.value.clearRect(0, 0, maskCanvas.value.width, maskCanvas.value.height)
  const { r, g, b } = hexToRgb(mask.color)
  maskCtx.value.fillStyle = `rgba(${r}, ${g}, ${b}, ${mask.opacity || maskOpacity.value})`
  maskCtx.value.beginPath()
  mask.points.forEach((pt, idx) => {
    if (idx === 0) maskCtx.value.moveTo(pt.x, pt.y)
    else maskCtx.value.lineTo(pt.x, pt.y)
  })
  maskCtx.value.closePath()
  maskCtx.value.fill()
  maskCtx.value.strokeStyle = mask.color
  maskCtx.value.lineWidth = 2
  maskCtx.value.stroke()
}

function addAnnotation() {
  if (!currentMask.value) {
    showStatus('请先生成分析结果', 'error')
    return
  }

  const type = annotationType.value
  const typeLabel = typeOptions.find((item) => item.value === type)?.label || type
  const record = {
    id: Date.now(),
    name: annotationName.value.trim() || '未命名标注',
    type,
    typeLabel,
    time: formatTimeLabel(currentTime.value),
    mask: { ...currentMask.value },
    points: {
      positive: [...positivePoints.value],
      negative: [...negativePoints.value],
    },
  }

  annotations.value = [record, ...annotations.value]
  selectedAnnotationId.value = record.id
  clearPoints()
  showStatus('标注已保存', 'success')
}

function selectAnnotation(item) {
  selectedAnnotationId.value = item.id
  currentMask.value = { ...item.mask }
  positivePoints.value = [...(item.points?.positive || [])]
  negativePoints.value = [...(item.points?.negative || [])]
  drawMask(item.mask)
}

function removeAnnotation(id) {
  annotations.value = annotations.value.filter((item) => item.id !== id)
  if (selectedAnnotationId.value === id) {
    selectedAnnotationId.value = null
    currentMask.value = null
    clearCanvas()
    clearPoints()
  }
}

function clearAllAnnotations() {
  annotations.value = []
  selectedAnnotationId.value = null
  currentMask.value = null
  clearCanvas()
  clearPoints()
}

function clearCanvas() {
  if (!maskCtx.value || !maskCanvas.value) return
  maskCtx.value.clearRect(0, 0, maskCanvas.value.width, maskCanvas.value.height)
}

function toggleTracking() {
  if (requireVideoBeforeAction()) return
  isTracking.value = !isTracking.value
  showStatus(`实时追踪已${isTracking.value ? '开启' : '关闭'}`, 'success')
}

function exportAnnotations() {
  if (requireVideoBeforeAction()) return
  if (!annotations.value.length) return
  const blob = new Blob([JSON.stringify(annotations.value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'video-annotations.json'
  link.click()
  URL.revokeObjectURL(url)
}

function exportSummary() {
  if (requireVideoBeforeAction()) return
  const payload = {
    project: currentProject.value,
    annotations: annotations.value,
    notes: notes.value,
    generatedSteps: generatedSteps.value,
    phaseAnalysis: phaseAnalysisResult.value,
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'analysis-summary.json'
  link.click()
  URL.revokeObjectURL(url)

  if (currentProject.value) {
    const updatedProject = {
      ...currentProject.value,
      notes: notes.value,
      status: '完成',
      updatedAt: new Date().toISOString(),
      updatedAtLabel: new Date().toLocaleString('zh-CN'),
    }
    currentProject.value = updatedProject
    saveProject(updatedProject)
    setActiveProject(updatedProject)
    showStatus('项目已标记为完成，并导出报告', 'success')
  }
}

function statusClass(status) {
  if (status === '草稿') return 'bg-amber-100 text-amber-700'
  if (status === '正在上传') return 'bg-sky-100 text-sky-700'
  if (status === '待分析') return 'bg-slate-100 text-slate-700'
  if (status === '正在分析') return 'bg-blue-100 text-blue-700'
  if (status === '分析完成' || status === '完成') return 'bg-emerald-100 text-emerald-700'
  if (status === '分析失败') return 'bg-red-100 text-red-700'
  return 'bg-slate-100 text-slate-700'
}

function getPolygonCenter(points) {
  if (!points.length) return { x: 0, y: 0 }
  const sum = points.reduce((acc, point) => ({ x: acc.x + point.x, y: acc.y + point.y }), { x: 0, y: 0 })
  return { x: sum.x / points.length, y: sum.y / points.length }
}

function generateMaskFromPoints(positive, negative) {
  if (!positive.length) return []
  const center = getPolygonCenter(positive)
  const avgDistance = positive.reduce((acc, point) => acc + Math.hypot(point.x - center.x, point.y - center.y), 0) / positive.length
  let radius = Math.max(40, avgDistance * 1.5)

  if (negative.length) {
    const nearest = negative.reduce((best, point) => {
      const distance = Math.hypot(point.x - center.x, point.y - center.y)
      return distance < best ? distance : best
    }, Infinity)
    radius = Math.max(24, Math.min(radius, nearest * 0.85))
  }

  const points = []
  for (let i = 0; i < 48; i += 1) {
    const angle = (i / 48) * Math.PI * 2
    const scale = radius * (0.7 + 0.2 * Math.sin(angle * 3))
    points.push({ x: center.x + scale * Math.cos(angle), y: center.y + scale * Math.sin(angle) })
  }
  return points
}

function hexToRgb(hex) {
  const stripped = hex.replace('#', '')
  const bigint = parseInt(stripped, 16)
  return {
    r: (bigint >> 16) & 255,
    g: (bigint >> 8) & 255,
    b: bigint & 255,
  }
}

function formatTimeLabel(value) {
  if (!Number.isFinite(value) || value < 0) return '00:00'
  const minutes = Math.floor(value / 60)
  const seconds = Math.floor(value % 60)
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function formatConfidence(value) {
  if (!Number.isFinite(value)) return '--'
  return `${Math.round(value * 100)}%`
}

function showStatus(message, type = 'success') {
  if (statusTimer) {
    window.clearTimeout(statusTimer)
  }
  statusMessage.value = message
  statusType.value = type
  statusTimer = window.setTimeout(() => {
    statusMessage.value = ''
    statusTimer = null
  }, 2400)
}

function parseTime(text) {
  const match = text.match(/^(\d{1,2}):(\d{2})$/)
  if (!match) return NaN
  const minutes = parseInt(match[1], 10)
  const seconds = parseInt(match[2], 10)
  return minutes * 60 + seconds
}

function parseTimeRange(text) {
  const parts = text.split('-').map((item) => item.trim()).filter(Boolean)
  if (!parts.length || parts.some((part) => part === '...')) {
    return null
  }

  const start = parseTime(parts[0])
  const end = parts[1] ? parseTime(parts[1]) : start
  if (!Number.isFinite(start) || !Number.isFinite(end)) {
    return null
  }

  return {
    startTime: Math.min(start, end),
    endTime: Math.max(start, end),
  }
}

function addNote() {
  if (requireVideoBeforeAction()) return
  const range = parseTimeRange(noteTimeInput.value.trim())
  if (!range) {
    showStatus('请先用计时器记录时间段，或输入 mm:ss - mm:ss 格式时间', 'error')
    return
  }
  if (!noteTextInput.value.trim()) {
    showStatus('请输入文字注释内容', 'error')
    return
  }
  notes.value = [
    ...notes.value,
    {
      id: Date.now(),
      time: range.startTime,
      startTime: range.startTime,
      endTime: range.endTime,
      text: noteTextInput.value.trim(),
    },
  ]
  persistProjectNotes()
  noteTextInput.value = ''
  clearAnnotationTimer()
  showStatus('文字注释已添加', 'success')
}

function formatNoteRange(note) {
  const start = note.startTime ?? note.time
  const end = note.endTime ?? note.time
  if (!Number.isFinite(end) || end === start) {
    return formatTimeLabel(start)
  }
  return `${formatTimeLabel(start)} - ${formatTimeLabel(end)}`
}

function playNoteLoop(note) {
  if (requireVideoBeforeAction()) return
  if (!videoEl.value) {
    showStatus('请先加载视频后再播放注释片段', 'error')
    return
  }

  if (activeLoopNoteId.value === note.id) {
    exitNoteLoop()
    return
  }

  const startTime = note.startTime ?? note.time
  const endTime = note.endTime ?? note.time
  if (!Number.isFinite(startTime) || !Number.isFinite(endTime) || endTime <= startTime) {
    showStatus('该注释没有有效的时间区间', 'error')
    return
  }

  activeLoopNoteId.value = note.id
  activeLoopRange.value = { startTime, endTime }
  videoEl.value.currentTime = startTime
  videoEl.value.play?.()
  showStatus(`正在循环播放注释片段 ${formatTimeLabel(startTime)} - ${formatTimeLabel(endTime)}`, 'success')
}

function exitNoteLoop() {
  if (requireVideoBeforeAction()) return
  activeLoopNoteId.value = null
  activeLoopRange.value = null
  showStatus('已退出注释片段循环播放', 'success')
}

function removeNote(id) {
  if (requireVideoBeforeAction()) return
  if (activeLoopNoteId.value === id) {
    activeLoopNoteId.value = null
    activeLoopRange.value = null
  }
  notes.value = notes.value.filter((item) => item.id !== id)
  persistProjectNotes()
}

function seekTo(seconds) {
  if (requireVideoBeforeAction()) return
  if (!videoEl.value) return
  videoEl.value.currentTime = seconds
  currentTime.value = seconds
}

onMounted(() => {
  currentProject.value = getActiveProject()
  notes.value = Array.isArray(currentProject.value?.notes) ? currentProject.value.notes : []
  phaseAnalysisResult.value = currentProject.value?.phaseAnalysis?.result || null
  phaseError.value = currentProject.value?.phaseAnalysis?.error || ''
  phaseJobStatus.value = currentProject.value?.phaseAnalysis?.status || ''

  if (currentProject.value?.videoUrl) {
    uploadedVideoUrl.value = currentProject.value.videoUrl
  } else if (currentProject.value?.hasVideo) {
    getProjectVideo(currentProject.value.id)
      .then((file) => {
        if (file) {
          projectVideoFile.value = file
          uploadedVideoUrl.value = URL.createObjectURL(file)
        } else {
          showStatus('未找到该项目的视频文件，请重新上传', 'error')
        }
      })
      .catch(() => {
        showStatus('项目视频加载失败，请重新上传', 'error')
      })
  }

  if (currentProject.value?.phaseAnalysis?.jobId && ['queued', 'running'].includes(currentProject.value.phaseAnalysis.status)) {
    syncProjectPhaseAnalysis(currentProject.value)
      .then((project) => {
        currentProject.value = project
        phaseAnalysisResult.value = project?.phaseAnalysis?.result || null
        phaseError.value = project?.phaseAnalysis?.error || ''
        phaseJobStatus.value = project?.phaseAnalysis?.status || ''
        if (['queued', 'running'].includes(project?.phaseAnalysis?.status)) {
          startPhasePolling()
        }
      })
      .catch(() => {
        startPhasePolling()
      })
  }

  if (maskCanvas.value) maskCtx.value = maskCanvas.value.getContext('2d')
  window.addEventListener('resize', setCanvasSize)
  setCanvasSize()
})

onBeforeUnmount(() => {
  stopPhasePolling()
  if (statusTimer) {
    window.clearTimeout(statusTimer)
    statusTimer = null
  }
  revokeUploadedVideoUrl()
  window.removeEventListener('resize', setCanvasSize)
  if (videoEl.value) {
    videoEl.value.pause()
    videoEl.value.src = ''
    videoEl.value.load()
  }
})

const analysisImageSrc =
  'data:image/svg+xml;charset=UTF-8,' +
  encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
      <defs>
        <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#0f172a"/>
          <stop offset="1" stop-color="#1d4ed8"/>
        </linearGradient>
      </defs>
      <rect width="1280" height="720" fill="url(#g)"/>
      <g fill="#ffffff" opacity="0.9" font-family="Segoe UI, Arial" text-anchor="middle">
        <text x="640" y="360" font-size="44" font-weight="700">CholecInsight 分析示例</text>
        <text x="640" y="420" font-size="20" opacity="0.85">请上传或选择项目视频开始分析</text>
      </g>
    </svg>
  `)
</script>

<style scoped>
.video-container {
  position: relative;
  background-color: #000;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.25);
}
.mask-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.annotation-timer {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 86px;
  justify-content: center;
  padding: 8px 10px;
  border-radius: 10px;
  background: #0f172a;
  color: white;
  border: 1px solid #1e293b;
  font-size: 13px;
  font-weight: 800;
}
.annotation-timer.recording {
  background: #dc2626;
  border-color: #b91c1c;
}
.points-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.point-dot {
  position: absolute;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
  border: 2px solid #fff;
}
.point-positive { background-color: rgba(34, 197, 94, 0.95); }
.point-negative { background-color: rgba(239, 68, 68, 0.95); }
.video-container,
.video-container video { cursor: default; }
.seg-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
  font-size: 13px;
  background: #f1f5f9;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
}
.seg-btn.primary { background: linear-gradient(135deg, #2563eb, #0ea5e9); color: white; border: none; }
.seg-btn-active { background: #e0f2fe; border-color: #bae6fd; }
.seg-btn-active.neg { background: #fee2e2; border-color: #fecdd3; }
.badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: #dcfce7;
  color: #166534;
  font-weight: 600;
  font-size: 13px;
}
.badge.ghost { background: #e2e8f0; color: #334155; }
.timeline-bar {
  position: relative;
  height: 10px;
  background-color: #e2e8f0;
  border-radius: 5px;
  overflow: hidden;
}
.timeline-bar .progress { height: 100%; }
.note-marker {
  position: absolute;
  top: -3px;
  width: 2px;
  height: 16px;
  background: #f59e0b;
  transform: translateX(-1px);
}
.note-form { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.note-time { width: 110px; }
.note-text { flex: 1 1 240px; }
.note-list { margin-top: 10px; display: grid; gap: 8px; }
.note-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background-color 0.18s ease;
}
.note-row:hover {
  border-color: #bfdbfe;
  background: #f8fafc;
}
.note-row.active-loop {
  border-color: #2563eb;
  background: #eff6ff;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}
.note-time-label { font-weight: 700; color: #0f172a; font-size: 13px; }
.note-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.loop-chip {
  padding: 4px 8px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}
.note-delete {
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fecdd3;
  border-radius: 8px;
  padding: 6px 8px;
}
.chart-container { height: 250px; }
.annotation-list { margin-top: 14px; border-top: 1px dashed #e2e8f0; padding-top: 10px; display: grid; gap: 10px; }
.annotation-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
}
.annotation-row.active { box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15); border-color: #bfdbfe; }
.dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
.time-chip { background: #e0f2fe; padding: 4px 8px; border-radius: 8px; display: inline-flex; align-items: center; }
.seg-mini {
  font-size: 12px;
  padding: 6px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  font-weight: 600;
}
.seg-mini.danger { background: #fef2f2; border-color: #fecdd3; color: #b91c1c; }
.empty { margin-top: 12px; padding: 12px; border: 1px dashed #e5e7eb; border-radius: 10px; color: #64748b; font-size: 13px; background: #f8fafc; }
.top-toast {
  position: fixed;
  top: 84px;
  left: 50%;
  z-index: 9999;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  max-width: min(560px, calc(100vw - 32px));
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 800;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.22);
  transform: translateX(-50%);
}
.top-toast.success {
  background: #ecfdf3;
  color: #166534;
  border: 1px solid #bbf7d0;
}
.top-toast.error {
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fecaca;
}
.toast-slide-enter-active,
.toast-slide-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.toast-slide-enter-from,
.toast-slide-leave-to {
  opacity: 0;
  transform: translate(-50%, -10px);
}
.status-box {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  font-weight: 600;
  font-size: 13px;
}
.status-box.success { background: #ecfdf3; color: #166534; border: 1px solid #bbf7d0; }
.status-box.error { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
.phase-progress-panel {
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  background: #eff6ff;
}
.phase-stage {
  font-weight: 800;
  color: #1e3a8a;
}
.phase-message {
  margin-top: 2px;
  font-size: 13px;
  color: #475569;
}
.phase-percent {
  font-weight: 800;
  color: #2563eb;
}
.phase-progress-track {
  height: 8px;
  margin-top: 12px;
  overflow: hidden;
  border-radius: 999px;
  background: #dbeafe;
}
.phase-progress-bar {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  transition: width 0.2s ease;
}
</style>
