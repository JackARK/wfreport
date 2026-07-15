import { reactive, watch } from 'vue'

const STORAGE_KEY = 'wfreport.workspace'

const fresh = () => ({
  step: 1,           // 1=upload, 2=fill, 3=preview, 4=export
  weekId: '',
  uploadMeta: null,  // { rows, 周起始日, 周结束日 }
  content: '',
  planItems: [],
  procurementItems: [],
  aiTexts: { week_compare: '', daily_summary: '' },
  narrativeOverrides: {},
})

const loaded = (() => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return fresh()
    const parsed = JSON.parse(raw)
    return { ...fresh(), ...parsed }
  } catch { return fresh() }
})()

export const workspace = reactive(loaded)

export function resetWorkspace() {
  Object.assign(workspace, fresh())
  persist()
}

// Load a persisted week from the backend into the live workspace store.
// Used by the History page; the user can then jump to step 4 and
// re-render the report without re-uploading anything.
export function loadHistoryWeek(payload) {
  if (!payload || !payload.week_id) return
  const ws = payload.workspace || {}
  workspace.weekId      = payload.week_id
  workspace.uploadMeta  = payload.uploadMeta || { rows: payload.rows, 周起始日: payload.周起始日, 周结束日: payload.周结束日 }
  workspace.content            = ws.content || ''
  workspace.planItems          = ws.plan_items || []
  workspace.procurementItems   = ws.procurement_items || []
  workspace.aiTexts            = {
    week_compare: (ws.narrative_overrides && ws.narrative_overrides.week_compare) || '',
    daily_summary: (ws.narrative_overrides && ws.narrative_overrides.daily_summary) || '',
  }
  // narrative_overrides from backend only contains brand/brand_share/product/new —
  // merge into our internal map so the step-3 editor + step-4 build pick them up.
  workspace.narrativeOverrides = Object.assign({}, ws.narrative_overrides || {})
  // viewing a historical week lands the user on step 4 — the report
  // can be regenerated or downloaded with zero further input.
  workspace.step = 4
  persist()
}

// Wipe user-entered content only — used after a re-upload of the same week_id
// so the new data isn't paired with stale plans / AI narratives / form text.
// Also flushes any in-flight debounced autosave so a queued save doesn't
// re-persist the wiped-out values.
let _wipeTimer = null
export function wipeContent() {
  if (_wipeTimer) { clearTimeout(_wipeTimer); _wipeTimer = null }
  flushAutosave()
  workspace.uploadMeta = null
  workspace.content = ''
  workspace.planItems = []
  workspace.procurementItems = []
  workspace.aiTexts = { week_compare: '', daily_summary: '' }
  workspace.narrativeOverrides = {}
  persist()
}

// ---- shared autosave debouncer ----
// Components call scheduleAutosave(saveFn); store coalesces concurrent calls so the
// backend isn't re-hit on every keystroke. callFlushAutosave() forces the pending save
// to run immediately and clears the timer — used after wipeContent.
const _autosaveQueue = []
let _autosaveTimer = null
export function scheduleAutosave(saveFn, dbPathOrWeekId) {
  _autosaveQueue.push({ saveFn, dbPathOrWeekId })
  clearTimeout(_autosaveTimer)
  _autosaveTimer = setTimeout(() => {
    const pending = _autosaveQueue.splice(0)
    _autosaveTimer = null
    // run the latest entry (last write wins)
    const last = pending[pending.length - 1]
    if (last && last.saveFn) last.saveFn()
  }, 800)
}
export function flushAutosave() {
  if (_autosaveTimer) {
    clearTimeout(_autosaveTimer)
    _autosaveTimer = null
    const pending = _autosaveQueue.splice(0)
    const last = pending[pending.length - 1]
    if (last && last.saveFn) last.saveFn()
  }
}

export function gotoStep(step) {
  workspace.step = step
  persist()
}

export function markStepDone(step) {
  if (workspace.step < step + 1) workspace.step = Math.min(4, step + 1)
  persist()
}

export function setWeek(weekId, uploadMeta) {
  workspace.weekId = weekId
  workspace.uploadMeta = uploadMeta
  persist()
}

export function setContent(text) { workspace.content = text; persist() }
export function setPlanItems(arr)  { workspace.planItems = arr;  persist() }
export function setProcurementItems(arr) { workspace.procurementItems = arr; persist() }
export function setAiTexts(t)      { Object.assign(workspace.aiTexts, t); persist() }
export function setNarrativeOverride(k, v) { workspace.narrativeOverrides[k] = v; persist() }

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      step: workspace.step,
      weekId: workspace.weekId,
      uploadMeta: workspace.uploadMeta,
      content: workspace.content,
      planItems: workspace.planItems,
      procurementItems: workspace.procurementItems,
      aiTexts: workspace.aiTexts,
      narrativeOverrides: workspace.narrativeOverrides,
    }))
  } catch {}
}

// cross-tab sync
window.addEventListener('storage', (e) => {
  if (e.key === STORAGE_KEY && e.newValue) {
    try { Object.assign(workspace, JSON.parse(e.newValue)) } catch {}
  }
})

// ---- step meta ----
export const STEP_META = [
  { id: 1, key: 'upload',  title: '上传销售明细',   short: '上传',
    desc: '选择本周 Excel · 自动派生平台 + week_id',
    next: '下一步 · 填写工作内容' },
  { id: 2, key: 'fill',    title: '填写本周内容与下周规划', short: '填写',
    desc: '记录本周工作要点与下周计划',
    next: '下一步 · 生成预览' },
  { id: 3, key: 'preview', title: '生成周报预览',   short: '预览',
    desc: 'KPI + 11 张图 + AI 文案 + 表格',
    next: '下一步 · 导出下载' },
  { id: 4, key: 'export',  title: '导出与下载',     short: '导出',
    desc: 'Excel + PPT + 整周打包',
    next: '完成 · 开始新一周' },
]

export function isStepReachable(step) {
  if (step === 1) return true
  if (!workspace.weekId) return false
  if (step === 2) return workspace.uploadMeta != null
  if (step === 3) return workspace.planItems.length > 0 || workspace.procurementItems.length > 0 || (workspace.content && workspace.content.trim().length > 0)
  if (step === 4) return true   // step 4 always reachable after step 3 visit
  return false
}

export function stepState(step) {
  if (workspace.step === step) return 'current'
  if (workspace.step > step)   return 'done'
  return isStepReachable(step) ? 'available' : 'pending'
}
