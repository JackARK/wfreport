<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick, inject } from 'vue'
import { upload } from '../api'

const props = defineProps({ open: Boolean, startTab: { type: String, default: 'upload' } })
const emit = defineEmits(['close', 'goto', 'use-sample', 'uploaded', 'tour-entered'])
const showToast = inject('showToast')

const idx = ref(0)
const targetRect = ref(null)
const tipPos = ref({ top: 0, left: 0, side: 'bottom', arrowX: '50%', arrowY: '50%' })
const usedSample = ref(false)
const loading = ref(false)
const skipFrom = ref(0) // first spotlight idx considered by progress

// ---- flow definition ----
const FLOW = [
  {
    id: 'welcome',
    modal: true,
    kind: 'welcome',
  },
  {
    id: 'shell',
    title: '界面总览',
    body: '左:主导航 · 中上:页面标题与周次标识 · 右下角:? 帮助按钮可重看引导',
    target: '.sidebar',
    side: 'right',
    primary: '下一步',
  },
  {
    id: 'upload',
    title: '导入数据',
    body: '拖放或点击上传本周 Excel,系统自动派生 平台 + week_id。',
    sub: ['毛利率按加权法计算 (Σ毛利 ÷ Σ金额)','同一周再次上传会覆盖历史'],
    target: '.dropzone',
    side: 'bottom',
    primary: '下一步',
  },
  {
    id: 'preview',
    tab: 'preview',
    title: '预览: KPI + 11 张图',
    body: '顶部 4 个 KPI(加权口径),下方 11 张图涵盖品牌 / 平台 / TOP / 新品 / 工厂。',
    sub: ['近三周对比 + 工厂 TOP15 以表格呈现','每张图都有独立卡片头(标题/描述/类型)'],
    target: '.kpi-grid',
    side: 'bottom',
    primary: '下一步',
    primaryKind: 'goto-config',
  },
  {
    id: 'config',
    tab: 'config',
    title: 'AI 配置: Prompt 模板',
    body: '4 张卡片对应 4 处 AI 文案生成,使用 Jinja2 变量语法。',
    sub: ['热加载: 保存即生效,无需重启','有改动时右上角 chip 提示「● 有未保存的改动」'],
    target: '.charts-grid',
    side: 'top',
    primary: '下一步',
    primaryKind: 'goto-generate',
  },
  {
    id: 'generate',
    tab: 'generate',
    title: '生成: 5 步工作流',
    body: '① 上周对比 ② 每日总结 ③ 采购要点 ④ 下周计划 ⑤ 一键生成',
    sub: ['① ② 直接生成文案','③ ④ 输入要点,「AI 结构化」变可编辑表格','⑤ 产出 Excel + PPT'],
    target: '.split',
    side: 'top',
    primary: '下一步',
  },
  {
    id: 'done',
    modal: true,
    kind: 'done',
  },
]

const current = computed(() => FLOW[idx.value])

// Effective progress counts only the spotlight sub-sequence the user is actually walking.
// Example: using sample → we jump to "preview" but progress should start at 1 / (remaining).
const spotlightSlice = computed(() => {
  const start = Math.max(0, skipFrom.value)
  const end = FLOW.length - 1 // exclude final modal
  return FLOW.slice(start, end + 1).filter(s => !s.modal)
})
const totalTour = computed(() => spotlightSlice.value.length)
const tourStep = computed(() => {
  let n = 0
  for (let i = Math.max(0, skipFrom.value); i <= idx.value; i++) {
    if (!FLOW[i].modal) n++
  }
  return n
})

// Map current idx → which slice index (for dot highlight)
const tourPosition = computed(() => {
  const slice = spotlightSlice.value
  const id = current.value.id
  return slice.findIndex(s => s.id === id)
})

watch(() => props.open, async (v) => {
  if (!v) { idx.value = 0; targetRect.value = null; return }
  usedSample.value = false
  loading.value = false
  skipFrom.value = 0
  await applyTab(current.value.tab)
  await nextTick()
  measureTarget()
})

watch(idx, async () => {
  await applyTab(current.value.tab)
  await nextTick()
  measureTarget()
})

async function applyTab(tab) {
  if (!tab) return
  if (current.value.id === 'preview' || current.value.id === 'config' || current.value.id === 'generate') {
    emit('goto', tab)
    emit('tour-entered', current.value.title) // tells App to show "→ 已进入" toast
    await new Promise(r => setTimeout(r, 350))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

function measureTarget() {
  const sel = current.value.target
  if (!sel) { targetRect.value = null; return }
  const el = document.querySelector(sel)
  if (!el) { targetRect.value = null; return }
  const r = el.getBoundingClientRect()
  targetRect.value = {
    top: r.top - 8,
    left: r.left - 8,
    width: r.width + 16,
    height: r.height + 16,
  }
  positionTip(r)
}

function positionTip(rect) {
  const side = current.value.side || 'bottom'
  const margin = 20
  const tipW = 380, tipH = 220
  let top = 0, left = 0, arrowX = '50%', arrowY = '50%'
  if (side === 'right') {
    left = rect.right + margin
    top  = rect.top + rect.height / 2 - tipH / 2
    arrowY = '50%'
  } else if (side === 'left') {
    left = rect.left - tipW - margin
    top  = rect.top + rect.height / 2 - tipH / 2
    arrowY = '50%'
  } else if (side === 'bottom') {
    top  = rect.bottom + margin
    left = rect.left + rect.width / 2 - tipW / 2
    arrowX = '50%'
  } else {
    top  = rect.top - tipH - margin
    left = rect.left + rect.width / 2 - tipW / 2
    arrowX = '50%'
  }
  const vw = window.innerWidth, vh = window.innerHeight
  const elW = Math.min(tipW, vw - 32)
  left = Math.max(16, Math.min(left, vw - elW - 16))
  top  = Math.max(80, Math.min(top,  vh - tipH - 24)) // keep below topbar (64px) + breathing
  tipPos.value = { top, left, side, arrowX, arrowY }
}

function next() {
  const kind = current.value.primaryKind
  if (kind === 'use-sample-and-start') { triggerSample(); return }
  if (kind === 'finish')                 { emit('close'); return }
  if (kind === 'goto-config')            { idx.value++; return }
  if (kind === 'goto-generate')          { idx.value++; return }
  if (idx.value < FLOW.length - 1) idx.value++
}
function prev() { if (idx.value > 0) idx.value-- }
function skip() { emit('close') }

// ---- Welcome actions ----
async function triggerSample() {
  loading.value = true
  try {
    const blob = await (await fetch('/sample.xlsx')).blob()
    const file = new File([blob], '本周.xlsx', { type: blob.type || 'application/octet-stream' })
    const r = await upload(file)
    usedSample.value = true
    showToast?.('示例数据已导入 · 已跳转到预览页', 'success')
    emit('uploaded', r.data.week_id)   // tell parent so PreviewPage gets weekId
    // jump to preview step & rebase progress so counter starts at 1
    const previewIdx = FLOW.findIndex(s => s.id === 'preview')
    idx.value = previewIdx
    skipFrom.value = previewIdx
  } catch (err) {
    showToast?.('示例加载失败,请手动上传', 'error')
    idx.value++ // proceed without sample
  } finally {
    loading.value = false
  }
}

async function skipToUploadManually() {
  // user has data already / wants to upload manually — skip sample, walk full tour
  skipFrom.value = 0
  idx.value++
}

function onKey(e) {
  if (!props.open) return
  if (e.key === 'Escape') { skip(); return }
  if (current.value.modal) return
  if (e.key === 'ArrowRight' || e.key === 'Enter') next()
  else if (e.key === 'ArrowLeft' && idx.value > 0) prev()
}

onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

function onResize() { if (props.open && targetRect.value) measureTarget() }
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="onb-overlay">
      <div class="onb-shroud" @click="skip"/>

      <!-- spotlight -->
      <div v-if="targetRect" class="onb-spotlight" :style="{
        top: targetRect.top + 'px',
        left: targetRect.left + 'px',
        width: targetRect.width + 'px',
        height: targetRect.height + 'px',
      }"/>

      <!-- Welcome modal (rich) -->
      <div v-if="current.modal && current.kind === 'welcome'" class="onb-welcome" @click.stop>
        <div class="hero">
          <div class="hero-logo">王</div>
          <h2>欢迎使用王凡周报生成器</h2>
          <p>供应链周报自动化的本地工具 · 6 步快速上手约 1 分钟</p>
        </div>
        <div class="body">
          <div class="value-list">
            <div class="value-item">
              <div class="ico">1</div>
              <div><b>导入 Excel</b><div class="d">上传本周销售明细, 自动派生平台 + week_id</div></div>
            </div>
            <div class="value-item">
              <div class="ico">2</div>
              <div><b>预览图表</b><div class="d">查看 KPI 与 11 张图(品牌/平台/TOP/工厂)</div></div>
            </div>
            <div class="value-item">
              <div class="ico">3</div>
              <div><b>配置 AI</b><div class="d">调整 4 处 prompt, 改完立即热加载</div></div>
            </div>
            <div class="value-item">
              <div class="ico">4</div>
              <div><b>生成报告</b><div class="d">一键产出 Excel (原生图表) + PPT (模板)</div></div>
            </div>
          </div>
          <div class="actions">
            <button class="btn btn-secondary" @click="skip">
              稍后再说
            </button>
            <button class="btn btn-secondary" @click="skipToUploadManually" :disabled="loading">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              我有数据,从引导开始
            </button>
            <button class="btn btn-primary" @click="triggerSample" :disabled="loading">
              <span v-if="loading" class="spinner"/>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
              用示例数据快速上手
            </button>
          </div>
        </div>
      </div>

      <!-- Done modal -->
      <div v-else-if="current.modal && current.kind === 'done'" class="onb-welcome" @click.stop>
        <div class="hero done">
          <div class="hero-logo">✓</div>
          <h2>引导完成</h2>
          <p>完整工作流已经了解。 随时可在右下角点击「?」重新打开</p>
        </div>
        <div class="body">
          <div class="hint-list">
            <div class="hint-row"><div class="hk">⌨</div><div><b>键盘</b><div class="d"><code>← →</code> 切换步骤 · <code>Esc</code> 关闭</div></div></div>
            <div class="hint-row"><div class="hk">⏵</div><div><b>重看引导</b><div class="d">侧栏底部链接, 或右下角「?」菜单</div></div></div>
            <div class="hint-row"><div class="hk">⚙</div><div><b>数据安全</b><div class="d">所有数据保存在本地 SQLite + output/ 目录</div></div></div>
          </div>
          <div class="actions" style="margin-top:20px">
            <button class="btn btn-secondary" @click="() => { skipFrom.value = 0; idx = 0 }">重新看一遍</button>
            <button class="btn btn-primary" @click="next">开始使用</button>
          </div>
        </div>
      </div>

      <!-- Spotlight tooltip -->
      <div
        v-else-if="targetRect"
        class="onb-tip"
        :class="'side-' + tipPos.side"
        :style="{
          top: tipPos.top + 'px',
          left: tipPos.left + 'px',
          '--arrow-x': tipPos.arrowX,
          '--arrow-y': tipPos.arrowY,
        }"
        @click.stop
      >
        <div class="arrow"/>
        <div class="tip-head">
          <span class="step-chip">{{ current.id }}</span>
          <span class="step-meta">{{ tourStep }} / {{ totalTour }}</span>
        </div>
        <h3>{{ current.title }}</h3>
        <p>{{ current.body }}</p>
        <ul v-if="current.sub">
          <li v-for="(s, i) in current.sub" :key="i">{{ s }}</li>
        </ul>

        <div class="onb-foot">
          <div class="dots">
            <span
              v-for="(s, i) in spotlightSlice"
              :key="s.id"
              class="dot"
              :class="{
                on: tourPosition === i,
                done: tourPosition !== -1 && i < tourPosition
              }"
            />
          </div>
          <div class="onb-actions">
            <button v-if="tourStep > 1" class="btn btn-ghost btn-sm" @click="prev">上一步</button>
            <button v-else class="btn btn-ghost btn-sm" @click="skip">跳过</button>
            <button class="btn btn-primary btn-sm" @click="next">
              {{ current.primary || '下一步' }}
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-left:4px"><polyline points="9 18 15 12 9 6"/></svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.step-chip {
  display: inline-block;
  padding: 2px 8px;
  background: var(--primary-soft);
  color: var(--primary);
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  font-family: var(--font-mono);
  letter-spacing: 0.3px;
}
.step-meta {
  font-size: 11px;
  color: var(--text-faint);
  font-family: var(--font-mono);
}
.tip-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
code {
  background: var(--bg-muted);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--text);
}
</style>
