<script setup>
import { ref, onMounted, inject } from 'vue'
import { listHistory, getWorkspace, reloadWorkspace, workspaceExportUrl } from '../api'
import { loadHistoryWeek, gotoStep } from '../store'

const showToastFn = inject('showToast')
const props = defineProps({ apiBase: { type: String, default: 'http://localhost:8000' } })
const emit = defineEmits(['close', 'opened'])

const weeks = ref([])
const loading = ref(false)
const expanded = ref(null)        // which row's dropdown is open
const opening = ref(null)         // week_id currently being opened

async function refresh() {
  loading.value = true
  try {
    const r = await listHistory()
    weeks.value = r.weeks || []
  } catch (e) {
    if (showToastFn) showToastFn('历史加载失败: ' + (e.message || ''), 'error')
    else showToast('历史加载失败: ' + (e.message || ''), 'error')
  } finally {
    loading.value = false
  }
}

onMounted(refresh)

// Inline import of the shared showToast via the store shim (fallback when
// no parent injection provided).
function toast(msg, kind) {
  if (showToastFn) showToastFn(msg, kind)
  else showToast(msg, kind)
}

async function openWeek(w) {
  opening.value = w.week_id
  try {
    // Backend may have lost its in-memory _state across restarts. Hit the
    // reload endpoint explicitly so subsequent preview/build steps work.
    await reloadWorkspace(w.week_id).catch(() => {})
    const r = await getWorkspace(w.week_id)
    loadHistoryWeek({
      week_id:     w.week_id,
      rows:        w.rows,
      周起始日:    w.周起始日,
      周结束日:    w.周结束日,
      workspace:   r.workspace,
      uploadMeta:  { rows: w.rows, 周起始日: w.周起始日, 周结束日: w.周结束日 },
    })
    gotoStep(4)
    toast('已加载历史 ' + w.week_id + ' · 进入第 4 步,可一键重新生成', 'success')
    emit('opened', w.week_id)
  } catch (e) {
    toast('打开失败: ' + (e?.response?.data?.detail || e.message), 'error')
  } finally {
    opening.value = null
    expanded.value = null
  }
}

function fmtMoney(n) { return '¥ ' + Number(n || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function fmtPct(n)   { return (Number(n || 0) * 100).toFixed(2) + '%' }
function fmtNum(n)   { return Number(n || 0).toLocaleString('zh-CN') }
function downloadUrl(u) { return props.apiBase + u }

function statusLabel(s) {
  if (!s) return '无内容'
  const parts = []
  if (s.content_chars > 0)   parts.push(`文本 ${s.content_chars} 字`)
  if (s.plan_items_count > 0) parts.push(`计划 ${s.plan_items_count} 条`)
  if (s.procurement_items_count > 0) parts.push(`采购 ${s.procurement_items_count} 条`)
  return parts.length ? parts.join(' · ') : '无内容'
}
</script>

<template>
  <div class="page-head">
    <div>
      <h2>历史记录</h2>
      <p>所有已持久化的周 · 一键重新打开任意一周,在第 4 步可零输入重新生成报告。</p>
    </div>
    <div class="flex items-center gap-2">
      <button class="btn btn-secondary" @click="refresh" :disabled="loading">
        <svg v-if="!loading" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
        刷新
      </button>
      <button class="btn btn-secondary" @click="emit('close')">← 返回工作流</button>
    </div>
  </div>

  <div v-if="loading && weeks.length === 0" class="charts-grid">
    <div v-for="i in 3" :key="i" class="card chart-card">
      <div class="card-head"><div class="skel" style="height:18px;width:180px"/></div>
      <div class="card-body"><div class="skel" style="height:120px"/></div>
    </div>
  </div>

  <div v-else-if="!loading && weeks.length === 0" class="card">
    <div class="empty">
      <div class="emoji">📭</div>
      <h3>暂无历史</h3>
      <p>上传第一份销售明细后,这里会自动出现历史列表。</p>
    </div>
  </div>

  <div v-else class="charts-grid">
    <div v-for="w in weeks" :key="w.week_id" class="card" style="overflow:visible">
      <div class="card-head">
        <div>
          <h3 style="display:flex;align-items:center;gap:8px">
            <span class="brand-logo" style="width:36px;height:36px;font-size:14px;border-radius:10px">{{ w.week_id.slice(-2) }}</span>
            <span>{{ w.week_id }}</span>
            <span class="chip mono" v-if="w.files.xlsx && w.files.pptx" style="background:var(--success-soft);color:var(--success)">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              文件齐
            </span>
            <span class="chip" v-else-if="w.files.xlsx || w.files.pptx" style="background:var(--warning-soft);color:var(--warning)">部分文件</span>
            <span class="chip" v-else style="background:var(--bg-muted);color:var(--text-muted)">仅数据</span>
          </h3>
          <div class="desc">{{ w.周起始日 }} → {{ w.周结束日 }} · {{ fmtNum(w.rows) }} 行</div>
        </div>
        <button class="btn btn-primary btn-sm" @click="openWeek(w)" :disabled="opening === w.week_id">
          <span v-if="opening === w.week_id" class="spinner"/>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>
          打开 → 第 4 步
        </button>
      </div>

      <div class="card-body">
        <!-- KPIs -->
        <div class="preview-mini-grid mb-3">
          <div class="preview-mini">
            <div class="lbl">销售金额</div>
            <div class="val" style="font-size:16px">{{ fmtMoney(w.销售额) }}</div>
          </div>
          <div class="preview-mini">
            <div class="lbl">毛利率</div>
            <div class="val" style="font-size:16px;color:var(--primary)">{{ fmtPct(w.销售毛利率) }}</div>
          </div>
          <div class="preview-mini">
            <div class="lbl">销售数量</div>
            <div class="val" style="font-size:16px">{{ fmtNum(w.销售数量) }}</div>
          </div>
          <div class="preview-mini">
            <div class="lbl">工作内容</div>
            <div class="val" style="font-size:13px">{{ statusLabel(w.workspace_summary) }}</div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-2 flex-wrap">
          <a class="btn btn-secondary btn-sm" :href="downloadUrl(w.urls.xlsx)" :class="{ disabled: !w.files.xlsx }" target="_blank" rel="noopener" :style="{ pointerEvents: w.files.xlsx ? 'auto' : 'none', opacity: w.files.xlsx ? 1 : 0.5 }">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            下载 Excel
          </a>
          <a class="btn btn-secondary btn-sm" :href="downloadUrl(w.urls.pptx)" :class="{ disabled: !w.files.pptx }" target="_blank" rel="noopener" :style="{ pointerEvents: w.files.pptx ? 'auto' : 'none', opacity: w.files.pptx ? 1 : 0.5 }">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            下载 PPT
          </a>
          <a class="btn btn-secondary btn-sm" :href="downloadUrl(w.urls.bundle)" target="_blank" rel="noopener" :style="{ pointerEvents: w.files.bundle ? 'auto' : 'none', opacity: w.files.bundle ? 1 : 0.5 }">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 16h-6a8 8 0 0 1-7-7V3a5 5 0 0 0-3.39 8.39"/></svg>
            下载 ZIP
          </a>
          <a class="btn btn-ghost btn-sm" :href="downloadUrl(w.urls.workspace)" target="_blank" rel="noopener">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            导出 workspace.json
          </a>
        </div>
      </div>
    </div>
  </div>

  <div class="alert alert-info mt-6">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
    <div>
      所有数据保存在本地 SQLite (<code class="mono">data/wfreport.db</code>) 与 <code class="mono">output/&lt;week_id&gt;/</code>。点「打开」可重新进入该周的工作流,无需再次上传 Excel。
    </div>
  </div>
</template>
