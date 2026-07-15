<script setup>
import { ref, provide, computed, onMounted } from 'vue'
import UploadPage from './components/UploadPage.vue'
import PreviewPage from './components/PreviewPage.vue'
import ConfigPage from './components/ConfigPage.vue'
import GeneratePage from './components/GeneratePage.vue'
import ToastHost from './components/ToastHost.vue'
import Onboarding from './components/Onboarding.vue'
import HelpButton from './components/HelpButton.vue'

const APP_VERSION = '1.1.0' // bump to re-trigger tour after this revision

const tab = ref('upload')
const weekId = ref('')
const toast = ref(null)
const flash = ref(null) // "→ 已进入 预览" page-change banner

function showToast(message, kind = 'info') {
  toast.value = { message, kind, id: Date.now() }
  setTimeout(() => { toast.value = null }, 3200)
}
provide('showToast', showToast)

const tabs = [
  { id: 'upload',   label: '上传',   desc: '导入本周 Excel' },
  { id: 'preview',  label: '预览',   desc: '图表与三周对比' },
  { id: 'config',   label: 'AI 配置', desc: 'Prompt 模板' },
  { id: 'generate', label: '生成',   desc: '采购与下周计划' },
]
const current = computed(() => tabs.find(t => t.id === tab.value))

function onDone(wid) { weekId.value = wid; tab.value = 'preview' }

const onbOpen = ref(false)
function openOnboarding()  { onbOpen.value = true }
function closeOnboarding() { onbOpen.value = false; rememberDismissed() }
function resetOnboarding() { onbOpen.value = true }
function gotoOnboardingTab(t) {
  if (tabs.find(x => x.id === t)) tab.value = t
}
function onTourEntered(title) {
  flash.value = { label: tab.value, title, id: Date.now() }
  setTimeout(() => { flash.value = null }, 2600)
}
function onSampleUploaded(wid) {
  weekId.value = wid
  tab.value = 'preview'
}

function rememberDismissed() {
  localStorage.setItem('wfreport.onboarding.dismissed', '1')
  localStorage.setItem('wfreport.onboarding.version', APP_VERSION)
}

onMounted(async () => {
  const dismissed = localStorage.getItem('wfreport.onboarding.dismissed') === '1'
  const storedVer = localStorage.getItem('wfreport.onboarding.version')
  if (dismissed && storedVer === APP_VERSION) return

  try {
    const r = await fetch('/api/history')
    const data = await r.json()
    const hasHistory = (data?.recent || []).length > 0
    if (hasHistory && dismissed) return
  } catch (_) {}

  setTimeout(() => { onbOpen.value = true }, 600)
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
    <div class="nav">
      <button
        v-for="t in tabs"
        :key="t.id"
        class="nav-item"
        :class="{ on: tab === t.id }"
        @click="tab = t.id"
      >
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <template v-if="t.id === 'upload'">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </template>
          <template v-else-if="t.id === 'preview'">
            <line x1="18" y1="20" x2="18" y2="10"/>
            <line x1="12" y1="20" x2="12" y2="4"/>
            <line x1="6" y1="20" x2="6" y2="14"/>
          </template>
          <template v-else-if="t.id === 'config'">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </template>
          <template v-else>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
          </template>
        </svg>
        <span>{{ t.label }}</span>
      </button>
    </div>
    <div class="sidebar-foot">
      <button class="replay-link" @click="openOnboarding" aria-label="重新打开新手引导">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <polygon points="10 8 16 12 10 16 10 8"/>
        </svg>
        重新打开引导
      </button>
      <div style="margin-top:8px">
        运行于 <code>:8000</code> · v{{ APP_VERSION }}
      </div>
    </div>
  </aside>

  <header class="topbar">
    <h1>{{ current.label }}</h1>
    <span class="sub">/ {{ current.desc }}</span>
    <span class="spacer"/>
    <span v-if="weekId" class="week-pill"><span class="dot"/>本周 {{ weekId }}</span>
    <span v-else class="week-pill empty">尚未上传</span>
  </header>

  <main class="main">
    <UploadPage   v-if="tab === 'upload'"   @done="onDone"/>
    <PreviewPage  v-else-if="tab === 'preview'"  :week-id="weekId"/>
    <ConfigPage   v-else-if="tab === 'config'"/>
    <GeneratePage v-else-if="tab === 'generate'" :week-id="weekId"/>
  </main>

  <!-- Page-change flash banner (onboarding-driven) -->
  <Teleport to="body">
    <div v-if="flash" class="page-flash" :key="flash.id">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
      <span>已进入 <b>{{ tabs.find(t => t.id === flash.label)?.label || flash.label }}</b></span>
    </div>
  </Teleport>

  <ToastHost :toast="toast"/>

  <HelpButton
    @open-onboarding="openOnboarding"
    @reset-onboarding="resetOnboarding"
  />

  <Onboarding
    :open="onbOpen"
    start-tab="upload"
    @close="closeOnboarding"
    @goto="gotoOnboardingTab"
    @uploaded="onSampleUploaded"
    @tour-entered="onTourEntered"
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
}
.replay-link:hover { background: var(--primary-soft); }
</style>
