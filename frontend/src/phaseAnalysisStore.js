import { getPhaseAnalysisJob } from './api/phaseAnalysis'
import { getActiveProject, getProjects, replaceProjects, saveProject, setActiveProject } from './projectStore'

function buildPhaseAnalysisState(job) {
  return {
    jobId: job.jobId,
    status: job.status,
    fileName: job.fileName,
    sampleSeconds: job.sampleSeconds,
    createdAt: job.createdAt,
    updatedAt: job.updatedAt,
    result: job.result || null,
    error: job.error || '',
  }
}

export function applyPhaseAnalysisToProject(project, job) {
  const phaseAnalysis = buildPhaseAnalysisState(job)
  return {
    ...project,
    phaseAnalysis,
    updatedAt: job.updatedAt || new Date().toISOString(),
    updatedAtLabel: new Date(job.updatedAt || Date.now()).toLocaleString('zh-CN'),
  }
}

export async function syncProjectPhaseAnalysis(project) {
  const jobId = project?.phaseAnalysis?.jobId
  const status = project?.phaseAnalysis?.status
  if (!jobId || !['queued', 'running'].includes(status)) {
    return project
  }

  const job = await getPhaseAnalysisJob(jobId)
  const updatedProject = applyPhaseAnalysisToProject(project, job)
  saveProject(updatedProject)

  const activeProject = getActiveProject()
  if (activeProject?.id === updatedProject.id) {
    setActiveProject(updatedProject)
  }

  return updatedProject
}

export async function syncRunningProjectsPhaseAnalysis() {
  const projects = getProjects()
  let changed = false
  const nextProjects = []

  for (const project of projects) {
    if (!project?.phaseAnalysis?.jobId || !['queued', 'running'].includes(project.phaseAnalysis.status)) {
      nextProjects.push(project)
      continue
    }

    try {
      const job = await getPhaseAnalysisJob(project.phaseAnalysis.jobId)
      nextProjects.push(applyPhaseAnalysisToProject(project, job))
      changed = true
    } catch {
      nextProjects.push(project)
    }
  }

  if (changed) {
    replaceProjects(nextProjects)
    const activeProject = getActiveProject()
    if (activeProject) {
      const refreshedActive = nextProjects.find((item) => item.id === activeProject.id)
      if (refreshedActive) {
        setActiveProject(refreshedActive)
      }
    }
  }

  return nextProjects
}
