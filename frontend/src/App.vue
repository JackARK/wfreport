<script setup>
import { ref, provide, computed, onMounted, watch } from 'vue'
import StepUpload   from './components/steps/StepUpload.vue'
import StepFill     from './components/steps/StepFill.vue'
import StepPreview  from './components/steps/StepPreview.vue'
import StepExport   from './components/steps/StepExport.vue'
import SettingsPage from './components/SettingsPage.vue'
import HistoryPage  from './components/HistoryPage.vue'
import ToastHost    from './components/ToastHost.vue'
import WorkflowProgress from './components/WorkflowProgress.vue'
import Onboarding       from './components/Onboarding.vue'
import HelpButton       from './components/HelpButton.vue'
import { workspace, STEP_META, stepState, gotoStep } from './store'

const APP_VERSION = '2.0.0'   // bumped: new workflow design

const toast = ref(null)
function showToast(message, kind = 'info') {
  toast.value = { message, kind, id: Date.now() }
  setTimeout(() => { toast.value = null }, 3200)
}
provide('showToast', showToast)

const view = ref('workflow')   // 'workflow' | 'settings' | 'history'

const onbOpen = ref(false)
const onbStartTab = ref('upload')

const tabs = [
  { id: 'upload',   label: '上传',   desc: '导入本周 Excel' },
  { id: 'fill',     label: '填写',   desc: '工作内容 + 计划' },
  { id: 'preview',  label: '预览',   desc: 'KPI + 11 张图' },
  { id: 'export',   label: '导出',   desc: 'Excel + PPT' },
]
const current = computed(() => tabs.find(t => t.id === ['upload','fill','preview','export'][workspace.step - 1]) || tabs[0])

function openSettings()   { view.value = 'settings' }
function closeSettings()  { view.value = 'workflow' }
function openHistory()    { view.value = 'history' }
function closeHistory()   { view.value = 'workflow' }
// When a historical week is opened from the history page, the store
// already jumped to step 4; just switch the view back to the workflow.
function onHistoryOpened() { view.value = 'workflow' }

function openOnb(tab = 'upload') {
  onbStartTab.value = tab
  onbOpen.value = true
}
function closeOnb() {
  onbOpen.value = false
  localStorage.setItem('wfreport.onboarding.dismissed', '1')
  localStorage.setItem('wfreport.onboarding.version', APP_VERSION)
}
function resetOnb() { onbOpen.value = true }

onMounted(async () => {
  const dismissed = localStorage.getItem('wfreport.onboarding.dismissed') === '1'
  const storedVer = localStorage.getItem('wfreport.onboarding.version')
  if (dismissed && storedVer === APP_VERSION) return
  try {
    const r = await fetch('/api/history')
    const data = await r.json()
    const hasHistory = (data?.recent || []).length > 0
    if (hasHistory && dismissed) return
  } catch {}
  setTimeout(() => onbOpen.value = true, 600)
})
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-logo">王</div>
      <div>
        <div class="brand-name">周报生成器</div>
        <div class="brand-sub">供应链 · 内部工具</div>
      </div>
    </div>

    <!-- Workflow step nav -->
    <div class="wf-side" v-if="view === 'workflow'">
      <div style="font-size:11px;color:var(--text-faint);text-transform:uppercase;letter-spacing:0.5px;padding:6px 12px;margin-top:4px">工作流</div>
      <button
        v-for="s in STEP_META"
        :key="s.id"
        class="wf-side-item"
        :class="{ done: stepState(s.id) === 'done', current: stepState(s.id) === 'current' }"
        :disabled="stepState(s.id) === 'pending'"
        @click="view === 'workflow' && stepState(s.id) !== 'pending' && gotoStep(s.id)"
      >
        <span class="num">
          <svg v-if="stepState(s.id) === 'done'" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          <template v-else>{{ s.id }}</template>
        </span>
        <span>{{ s.short }}</span>
      </button>
    </div>

    <div class="sidebar-foot">
      <button class="replay-link" @click="view === 'history' ? closeHistory() : openHistory()" :style="view === 'history' ? { color: 'var(--primary)', background: 'var(--primary-soft)' } : {}">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 3v18h18"/>
          <path d="M7 14l3-3 4 4 6-6"/>
          <path d="M14 9h6v6"/>
        </svg>
        {{ view === 'history' ? '↩ 返回工作流' : '📚 历史记录' }}
      </button>
      <button class="replay-link" @click="openOnb(tabs[workspace.step-1]?.id || 'upload')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/>
        </svg>
        重新打开引导
      </button>
      <div style="margin-top:6px">
        <button class="replay-link" @click="view === 'workflow' ? openSettings() : closeSettings()" style="color:var(--text-muted)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          {{ view === 'settings' ? '↩ 返回工作流' : 'AI 配置 (Prompts)' }}
        </button>
      </div>
      <div style="margin-top:8px">
        运行于 <code>:8000</code> · v{{ APP_VERSION }}
      </div>
    </div>
  </aside>

  <header class="topbar" v-if="view === 'workflow'">
    <h1>{{ current?.label || '' }}</h1>
    <span class="sub">/ {{ current?.desc || '' }}</span>
    <span class="spacer"/>
    <span v-if="workspace.weekId" class="week-pill"><span class="dot"/>本周 {{ workspace.weekId }}</span>
    <span v-else class="week-pill empty">尚未上传</span>
  </header>

  <header class="topbar" v-else-if="view === 'settings'">
    <h1>AI 配置</h1>
    <span class="sub">/ Prompt 模板</span>
    <span class="spacer"/>
    <span class="week-pill empty">侧栏返回工作流</span>
  </header>

  <header class="topbar" v-else-if="view === 'history'">
    <h1>历史记录</h1>
    <span class="sub">/ 所有已持久化的周</span>
    <span class="spacer"/>
    <span class="week-pill empty">侧栏返回工作流</span>
  </header>

  <main class="main">
    <WorkflowProgress v-if="view === 'workflow'"/>

    <StepUpload   v-if="view === 'workflow' && workspace.step === 1"/>
    <StepFill     v-else-if="view === 'workflow' && workspace.step === 2" :week-id="workspace.weekId"/>
    <StepPreview  v-else-if="view === 'workflow' && workspace.step === 3" :week-id="workspace.weekId"/>
    <StepExport   v-else-if="view === 'workflow' && workspace.step === 4" :week-id="workspace.weekId"/>

    <SettingsPage v-if="view === 'settings'" @close="closeSettings"/>
    <HistoryPage  v-if="view === 'history'"  @close="closeHistory" @opened="onHistoryOpened"/>
  </main>

  <ToastHost :toast="toast"/>

  <HelpButton @open-onboarding="openOnb(onbStartTab)" @reset-onboarding="resetOnb"/>

  <Onboarding
    :open="onbOpen"
    :start-tab="onbStartTab"
    @close="closeOnb"
  />
</template>

<style scoped>
.replay-link {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: none;
  cursor: pointer;
  font: inherit;
  font-size: 12.5px;
  color: var(--primary);
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  transition: background 0.15s;
  width: 100%;
  text-align: left;
}
.replay-link:hover { background: var(--primary-soft); }
</style>
