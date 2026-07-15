<script setup>
import { ref, computed, inject } from 'vue'
import { upload } from '../../api'
import { setWeek, markStepDone, gotoStep, STEP_META } from '../../store'

const emit = defineEmits(['forward'])
const showToast = inject('showToast')

const file = ref(null)
const dragging = ref(false)
const busy = ref(false)
const errorMsg = ref('')
const uploadResult = ref(null)

const next = computed(() => STEP_META[0])

async function pickFile(e) {
  const f = e.target.files?.[0]
  if (!f) return
  if (!/\.(xlsx|csv|xls)$/i.test(f.name)) {
    errorMsg.value = '请选择 .xlsx / .csv 文件'
    return
  }
  file.value = f; errorMsg.value = ''; uploadResult.value = null
}
function onDrop(e) {
  e.preventDefault(); dragging.value = false
  const f = e.dataTransfer.files?.[0]
  if (f && /\.(xlsx|csv|xls)$/i.test(f.name)) { file.value = f; errorMsg.value = ''; uploadResult.value = null }
  else if (f) errorMsg.value = '请选择 .xlsx / .csv 文件'
}
function onDragOver(e) { e.preventDefault(); dragging.value = true }
function onDragLeave()   { dragging.value = false }
function clearFile()     { file.value = null; uploadResult.value = null; errorMsg.value = '' }

async function submit() {
  if (!file.value) { errorMsg.value = '请先选择文件'; return }
  busy.value = true; errorMsg.value = ''
  try {
    const r = await upload(file.value)
    uploadResult.value = r.data
    setWeek(r.data.week_id, { rows: r.data.rows, 周起始日: r.data.周起始日, 周结束日: r.data.周结束日 })
    showToast?.('已上传,正在准备下一步', 'success')
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || err.message || '上传失败'
  } finally { busy.value = false }
}

async function useSample() {
  busy.value = true; errorMsg.value = ''
  try {
    const blob = await (await fetch('/sample.xlsx')).blob()
    const f = new File([blob], '本周.xlsx', { type: blob.type || 'application/octet-stream' })
    file.value = f
    const r = await upload(f)
    uploadResult.value = r.data
    setWeek(r.data.week_id, { rows: r.data.rows, 周起始日: r.data.周起始日, 周结束日: r.data.周结束日 })
    showToast?.('示例已上传', 'success')
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || err.message || '示例上传失败'
  } finally { busy.value = false }
}

function goForward() { if (uploadResult.value) { markStepDone(1); gotoStep(2) } }

function fmtBytes(n) {
  if (n < 1024) return n + ' B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1024 / 1024).toFixed(2) + ' MB'
}
</script>

<template>
  <div class="step-head">
    <div class="badge">1</div>
    <div>
      <h2>上传本周销售明细</h2>
      <p>支持 .xlsx / .csv · 自动派生 <code class="mono">平台</code> + <code class="mono">week_id</code>(ISO 周,例 <code class="mono">2026-W27</code>)</p>
    </div>
    <div class="right">
      <span v-if="uploadResult" class="chip" style="background:var(--success-soft);color:var(--success)">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
        已上传
      </span>
    </div>
  </div>

  <div style="padding: 0 32px">
    <div class="card mb-4">
      <div class="card-body">
        <label
          class="dropzone"
          :class="{ drag: dragging, 'has-file': !!file && !uploadResult }"
          @drop="onDrop" @dragover="onDragOver" @dragleave="onDragLeave"
        >
          <input type="file" accept=".xlsx,.xls,.csv" @change="pickFile" style="position:absolute;width:1px;height:1px;opacity:0;pointer-events:none"/>
          <template v-if="!file && !uploadResult">
            <div class="icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
            </div>
            <h4>拖拽文件至此处 或 点击选择</h4>
            <p>本周销售明细 Excel · 毛利率按 <b>加权</b>法计算</p>
          </template>
          <template v-else-if="file && !uploadResult">
            <div class="icon" style="background:#ecfdf5;color:var(--success)">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
              </svg>
            </div>
            <h4>{{ file.name }}</h4>
            <p class="file-meta">{{ fmtBytes(file.size) }} · 已就绪</p>
            <div class="mt-4"><button type="button" class="btn btn-secondary btn-sm" @click.prevent.stop="clearFile">替换文件</button></div>
          </template>
          <template v-else>
            <div class="icon" style="background:var(--success-soft);color:var(--success)">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </div>
            <h4>解析成功</h4>
            <p class="file-meta mono">
              week_id: <b>{{ uploadResult.week_id }}</b> · {{ uploadResult.rows.toLocaleString() }} 行 · {{ uploadResult.周起始日 }} → {{ uploadResult.周结束日 }}
            </p>
          </template>
        </label>

        <div v-if="errorMsg" class="alert alert-danger mt-4">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <div>{{ errorMsg }}</div>
        </div>

        <div class="flex items-center gap-3 mt-4" v-if="!uploadResult">
          <button class="btn btn-primary btn-lg" @click="submit" :disabled="!file || busy">
            <span v-if="busy" class="spinner"/> 上传并解析
          </button>
          <span class="muted">·</span>
          <button class="btn btn-ghost" @click="useSample" :disabled="busy">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
            用示例数据
          </button>
          <span class="muted" style="margin-left:auto;font-size:12.5px">示例: 本周有 18,837 行 · 周一-周日</span>
        </div>
      </div>
    </div>
  </div>

  <div class="continue-bar" v-if="uploadResult">
    <div class="hint">
      <b>已就绪。</b> 系统已解析 {{ uploadResult.rows.toLocaleString() }} 行销售数据。下一步将填写本周工作内容与下周规划。
    </div>
    <button class="btn btn-ghost" @click="uploadResult=null; file=null">重新上传</button>
    <button class="btn btn-primary btn-lg" @click="goForward">
      下一步: 填写工作内容
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-left:6px"><polyline points="9 18 15 12 9 6"/></svg>
    </button>
  </div>
</template>

<style scoped>
.dropzone { display: block; position: relative; }
.icon {
  width: 48px; height: 48px;
  margin: 0 auto 12px;
  display: grid; place-items: center;
  border-radius: 14px;
  background: var(--primary-soft);
  color: var(--primary);
  font-size: 24px;
}
.dropzone h4 { margin: 0 0 4px; font-size: 15px; }
.dropzone p  { margin: 0; color: var(--text-muted); font-size: 12.5px; }
</style>
