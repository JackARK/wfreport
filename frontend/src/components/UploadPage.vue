<script setup>
import { ref, inject } from 'vue'
import { upload } from '../api'

const emit = defineEmits(['done'])
const showToast = inject('showToast')

const file = ref(null)
const dragging = ref(false)
const busy = ref(false)
const result = ref(null)
const errorMsg = ref('')

function pickFile(e) {
  const f = e.target.files?.[0]
  if (f) {
    file.value = f
    errorMsg.value = ''
    result.value = null
  }
}
function onDrop(e) {
  e.preventDefault()
  dragging.value = false
  const f = e.dataTransfer.files?.[0]
  if (f && /\.(xlsx|csv|xls)$/i.test(f.name)) {
    file.value = f
    errorMsg.value = ''
    result.value = null
  } else if (f) {
    errorMsg.value = '请选择 .xlsx / .csv 文件'
  }
}
function onDragOver(e) { e.preventDefault(); dragging.value = true }
function onDragLeave()   { dragging.value = false }
function clearFile()     { file.value = null; result.value = null; errorMsg.value = '' }

async function submit() {
  if (!file.value) { errorMsg.value = '请先选择文件'; return }
  busy.value = true; errorMsg.value = ''
  try {
    const r = await upload(file.value)
    result.value = r.data
    showToast?.('上传成功,正在解析数据…', 'success')
    setTimeout(() => emit('done', r.data.week_id), 600)
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || err.message || '上传失败'
  } finally {
    busy.value = false
  }
}

function fmtBytes(n) {
  if (n < 1024) return n + ' B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1024 / 1024).toFixed(2) + ' MB'
}
</script>

<template>
  <div class="page-head">
    <div>
      <h2>导入本周销售明细</h2>
      <p>支持 .xlsx / .csv · 上传后会派生 <code class="mono">平台</code> 与 <code class="mono">week_id</code>，并写入 SQLite 历史。</p>
    </div>
  </div>

  <div class="card mb-4">
    <div class="card-body">
      <label
        class="dropzone"
        :class="{ drag: dragging, 'has-file': !!file && !result }"
        @drop="onDrop"
        @dragover="onDragOver"
        @dragleave="onDragLeave"
      >
        <input type="file" accept=".xlsx,.xls,.csv" @change="pickFile" style="display:none"/>
        <template v-if="!file">
          <div class="icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          </div>
          <h4>拖拽文件至此处 或 点击选择</h4>
          <p>本周销售明细 Excel · 已自动派生平台 / week_id</p>
        </template>
        <template v-else>
          <div class="icon" style="background:#ecfdf5;color:#10b981">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="9" y1="13" x2="15" y2="13"/>
              <line x1="9" y1="17" x2="15" y2="17"/>
            </svg>
          </div>
          <h4>{{ file.name }}</h4>
          <p class="file-meta">{{ fmtBytes(file.size) }} · 已就绪</p>
          <div class="mt-4">
            <button type="button" class="btn btn-secondary btn-sm" @click.prevent.stop="clearFile">替换文件</button>
          </div>
        </template>
      </label>

      <div v-if="errorMsg" class="alert alert-danger mt-4">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <div>{{ errorMsg }}</div>
      </div>

      <div class="flex items-center gap-3 mt-4">
        <button class="btn btn-primary btn-lg" @click="submit" :disabled="!file || busy">
          <span v-if="busy" class="spinner"/> 上传并解析
        </button>
        <span class="muted">解析后会自动跳转到预览页</span>
      </div>
    </div>
  </div>

  <div v-if="result" class="alert alert-success">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
    <div>
      解析完成 · <b class="mono">{{ result.week_id }}</b> ·
      <span class="mono">{{ result.周起始日 }} → {{ result.周结束日 }}</span> ·
      共 <b class="mono">{{ result.rows.toLocaleString() }}</b> 行
    </div>
  </div>

  <div class="card mt-6">
    <div class="card-head">
      <div>
        <h3>使用说明</h3>
        <div class="desc">从导入到产出的标准流程</div>
      </div>
    </div>
    <div class="card-body">
      <div class="charts-grid">
        <div v-for="(s, i) in [
          { n: 1, t: '导入 Excel', d: '上传本周销售明细; 系统自动派生 平台 + week_id, 写入 SQLite。' },
          { n: 2, t: '预览图表',  d: '查看汇总、每日、品牌、平台、店铺 / 产品 TOP 热力、新品与工厂等 11 张图。' },
          { n: 3, t: '调整 Prompt', d: '在「AI 配置」页调整 4 处 prompt, 热加载无需重启。' },
          { n: 4, t: '生成报告',   d: 'AI 润色采购与下周计划, 一键产出 Excel + PPT, 文件位于 <code>output/&lt;week_id&gt;/</code>。' },
        ]" :key="i" style="display:flex;gap:14px;padding:8px 4px">
          <div class="brand-logo" style="flex:none">{{ s.n }}</div>
          <div>
            <div style="font-weight:600;margin-bottom:2px">{{ s.t }}</div>
            <div class="muted" style="font-size:12.5px" v-html="s.d"/>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dropzone { display: block; }
.dropzone input[type=file] {
  position: absolute;
  width: 1px; height: 1px;
  opacity: 0;
  pointer-events: none;
}
</style>
