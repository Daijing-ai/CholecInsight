<template>
  <div class="container mx-auto px-4 py-6">
    <section class="bg-white rounded-lg shadow-md p-6 mb-6">
      <h1 class="text-3xl font-bold text-gray-800 mb-2">上传页</h1>
      <p class="text-gray-600">在进入分析前，先填写视频项目描述，后续首页和分析页都会使用这些信息。</p>
    </section>

    <section class="bg-white rounded-lg shadow-md p-6">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="space-y-4">
          <div>
            <label class="input-label">项目名称</label>
            <input v-model="form.title" class="input" placeholder="例如：LC-病例-001" />
          </div>
          <div>
            <label class="input-label">术式名称</label>
            <input v-model="form.procedure" class="input" placeholder="例如：腹腔镜胆囊切除术" />
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="input-label">术者</label>
              <input v-model="form.surgeon" class="input" placeholder="输入术者姓名" />
            </div>
            <div>
              <label class="input-label">科室</label>
              <input v-model="form.department" class="input" placeholder="例如：肝胆外科" />
            </div>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="input-label">手术日期</label>
              <input v-model="form.date" type="date" class="input" />
            </div>
            <div>
              <label class="input-label">视频时长</label>
              <input v-model="form.duration" class="input" placeholder="例如：32min" />
            </div>
          </div>
          <div>
            <label class="input-label">项目描述</label>
            <textarea v-model="form.description" class="input min-h-[140px]" placeholder="填写病例背景、教学目的、关注重点等"></textarea>
          </div>
        </div>

        <div class="space-y-4">
          <div class="border border-dashed border-slate-300 rounded-xl p-6 bg-slate-50">
            <h2 class="text-lg font-semibold text-slate-800 mb-3">视频文件</h2>
            <button class="btn-primary mb-4" @click="triggerUpload">
              <i class="fas fa-video mr-2"></i>选择手术视频
            </button>
            <input ref="fileInputRef" type="file" accept="video/*" class="hidden" @change="onFileSelected" />
            <p class="text-sm text-slate-500">支持本地视频上传，后续分析页将直接读取当前会话中的视频文件。</p>

            <div v-if="form.fileName" class="mt-4 text-sm text-slate-700">
              <p><span class="text-slate-400">文件名：</span>{{ form.fileName }}</p>
            </div>
          </div>

          <div class="border border-slate-200 rounded-xl overflow-hidden bg-black">
            <video v-if="form.videoUrl" :src="form.videoUrl" class="w-full h-[280px] object-cover" controls></video>
            <div v-else class="h-[280px] flex items-center justify-center text-slate-400 bg-slate-900">
              上传后可在这里预览视频
            </div>
          </div>

          <div class="flex gap-3 flex-wrap">
            <button class="btn-primary" @click="saveAndGoAnalysis">
              <i class="fas fa-save mr-2"></i>保存并进入分析
            </button>
            <router-link to="/" class="btn-secondary">
              <i class="fas fa-house mr-2"></i>返回首页
            </router-link>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getProjects, saveProject, setActiveProject } from '../projectStore'

const router = useRouter()
const route = useRoute()
const fileInputRef = ref(null)
const form = ref({
  id: '',
  title: '',
  procedure: '',
  surgeon: '',
  department: '',
  date: '',
  duration: '',
  description: '',
  fileName: '',
  videoUrl: '',
  status: '待分析',
})

function triggerUpload() {
  fileInputRef.value?.click()
}

function onFileSelected(event) {
  const file = event.target.files?.[0]
  if (!file) return
  form.value.fileName = file.name
  form.value.videoUrl = URL.createObjectURL(file)
}

function saveAndGoAnalysis() {
  const now = new Date()
  const project = {
    ...form.value,
    id: form.value.id || `project-${now.getTime()}`,
    updatedAt: now.toISOString(),
    updatedAtLabel: now.toLocaleString('zh-CN'),
  }

  saveProject(project)
  setActiveProject(project)
  router.push('/analysis')
}

function loadProjectForEdit(id) {
  const existing = getProjects().find((item) => item.id === id)
  if (!existing) return
  form.value = {
    ...form.value,
    ...existing,
    videoUrl: existing.videoUrl || '',
  }
}

onMounted(() => {
  const editId = route.query.id
  if (typeof editId === 'string' && editId) {
    loadProjectForEdit(editId)
  }
})
</script>
