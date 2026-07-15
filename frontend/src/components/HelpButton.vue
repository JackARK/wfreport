<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

defineProps({ appVersion: { type: String, default: '1.0.0' } })
const emit = defineEmits(['open-onboarding', 'reset-onboarding'])

const open = ref(false)

function toggle() { open.value = !open.value }
function close()  { open.value = false }

function openOnboarding()  { emit('open-onboarding');  close() }
function resetOnboarding() {
  localStorage.removeItem('wfreport.onboarding.dismissed')
  localStorage.removeItem('wfreport.onboarding.version')
  emit('reset-onboarding')
  close()
}

function onDocClick(e) {
  if (!open.value) return
  if (!e.target.closest('.fab') && !e.target.closest('.fab-menu')) close()
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))

function onKey(e) { if (e.key === 'Escape') close() }
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div style="position:fixed;bottom:24px;right:24px;z-index:80">
    <transition name="fab">
      <div v-if="open" class="fab-menu" @click.stop>
        <button class="fab-item" @click="openOnboarding">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <polygon points="10 8 16 12 10 16 10 8"/>
          </svg>
          <div class="text">
            <span>重新打开引导</span>
            <span class="desc">约 1 分钟走完完整工作流</span>
          </div>
        </button>
        <button class="fab-item" @click="resetOnboarding">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 12a9 9 0 1 0 3-6.7L3 8"/>
            <polyline points="3 3 3 8 8 8"/>
          </svg>
          <div class="text">
            <span>重置引导</span>
            <span class="desc">下次刷新页面再次自动弹出</span>
          </div>
        </button>
        <hr class="sep" style="margin:6px 4px"/>
        <div class="fab-item" style="cursor:default">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="16" x2="12" y2="12"/>
            <line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
          <div class="text">
            <span>关于</span>
            <span class="desc">王凡周报生成器 · v{{ appVersion }}</span>
          </div>
        </div>
      </div>
    </transition>

    <button class="fab" :class="{ open }" @click.stop="toggle" aria-label="帮助">
      <svg v-if="!open" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
        <line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
      <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"/>
        <line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
  </div>
</template>

<style scoped>
.fab-enter-active, .fab-leave-active { transition: opacity 0.18s, transform 0.18s; }
.fab-enter-from, .fab-leave-to { opacity: 0; transform: translateY(6px) scale(0.96); }
</style>
