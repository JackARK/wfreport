<script setup>
import { ref, computed, watch, onMounted, inject } from 'vue'
import { buildFull, getWorkspace, downloadBundle, dl } from '../../api'
import { workspace, resetWorkspace, gotoStep } from '../../store'

const showToast = inject('showToast')
const props = defineProps({ weekId: String })

const building = ref(false)
const built    = ref({ xlsx: false, ppt: false })
const errMsg   = ref('')

async function refresh() {
  if (!props.weekId) return
  try {
    const r = await getWorkspace(props.weekId)
    const g = r.generated || {}
    built.value = { xlsx: !!g.xlsx_exists, ppt: !!g.ppt_exists }
  } catch {}
}
watch(() => props.weekId, refresh, { immediate: true })
onMounted(refresh)

async function buildAll() {
  if (!props.weekId) { showToast?.('请先上传数据', 'error'); return }
  building.value = true; errMsg.value = ''
  try {
    const r = await buildFull(props.weekId, { ai_texts: workspace.aiTexts })
    built.value = { xlsx: !!r.xlsx_url, ppt: !!r.ppt_url }
    showToast?.('Excel + PPT 已生成', 'success')
    await refresh()
  } catch (err) {
    errMsg.value = err?.response?.data?.detail || err.message || '生成失败'
  } finally {
    building.value = false
  }
}

function bundleHref() { return downloadBundle(props.weekId) }
function xlsxHref()   { return dl(props.weekId, props.weekId + '.xlsx') }
function pptHref()    { return dl(props.weekId, props.weekId + '.pptx') }

function startOver() {
  resetWorkspace()
  showToast?.('已重置,可开始下一周', 'info')
  gotoStep(1)
}

const stepsDone = computed(() => ({
  upload:   !!workspace.uploadMeta,
  fill:     (workspace.planItems.length + workspace.procurementItems.length) > 0 || (workspace.content && workspace.content.trim().length > 0),
  aiEdit:   !!workspace.aiTexts.week_compare || !!workspace.aiTexts.daily_summary,
  build:    !!built.value.xlsx || !!built.value.ppt,
}))
</script>

<template>
  <div class="step-head">
    <div class="badge">4</div>
    <div>
      <h2>导出与下载</h2>
      <p>点击「一键生成」渲染 Excel + PPT,生成后可单独下载或打包下载。文件保存在 <code class="mono">output/{{ weekId }}/</code>。</p>
    </div>
    <div class="right"/>
  </div>

  <div style="padding: 0 32px">
    <!-- 准备状态 -->
    <div class="kpi-grid mb-4">
      <div class="kpi" :class="stepsDone.upload ? 'acc-3' : ''">
        <div class="kpi-label">① 数据</div>
        <div class="kpi-val" :style="stepsDone.upload ? 'font-size:14px' : ''">{{ stepsDone.upload ? '已上传' : '未上传' }}</div>
        <div class="kpi-foot">本周销售明细已就绪</div>
      </div>
      <div class="kpi" :class="stepsDone.fill ? 'acc-3' : ''">
        <div class="kpi-label">② 工作内容</div>
        <div class="kpi-val" :style="stepsDone.fill ? 'font-size:14px' : ''">{{ stepsDone.fill ? '已填写' : '未填写' }}</div>
        <div class="kpi-foot">本周 / 采购 / 下周计划</div>
      </div>
      <div class="kpi" :class="stepsDone.aiEdit ? 'acc-3' : ''">
        <div class="kpi-label">③ AI 文案</div>
        <div class="kpi-val" :style="stepsDone.aiEdit ? 'font-size:14px' : ''">{{ stepsDone.aiEdit ? '已生成' : '未生成' }}</div>
        <div class="kpi-foot">上周对比 / 每日总结</div>
      </div>
      <div class="kpi" :class="stepsDone.build ? 'acc-3' : ''">
        <div class="kpi-label">④ 文件</div>
        <div class="kpi-val" :style="stepsDone.build ? 'font-size:14px' : ''">{{ stepsDone.build ? '已生成' : '未生成' }}</div>
        <div class="kpi-foot">Excel + PPT</div>
      </div>
    </div>

    <!-- 一键生成 -->
    <div class="card mb-4">
      <div class="card-body" style="display:flex;align-items:center;gap:18px;flex-wrap:wrap">
        <div style="flex:1;min-width:240px">
          <h3 style="margin:0 0 4px;font-size:15px">一键渲染</h3>
          <p class="muted" style="margin:0;font-size:12.5px">首次渲染约 30-60 秒(基于 kaleido 进程)</p>
        </div>
        <button class="btn btn-primary btn-lg" @click="buildAll" :disabled="building">
          <span v-if="building" class="spinner"/>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
          </svg>
          {{ building ? '渲染中…' : '一键生成 Excel + PPT' }}
        </button>
      </div>
    </div>

    <div v-if="errMsg" class="alert alert-danger mb-4">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      <div>{{ errMsg }}</div>
    </div>

    <!-- 下载 -->
    <div class="export-cards mb-4">
      <div class="export-card" :class="{ empty: !built.xlsx }">
        <div class="logo" style="background:linear-gradient(135deg,#10b981,#06b6d4)">XLS</div>
        <h3>Excel 周报</h3>
        <p>多 sheet + 原生图表 + 周内容 + 采购 + 下周计划</p>
        <a class="btn btn-primary dl-btn" :href="xlsxHref()" :class="{ disabled: !built.xlsx }" target="_blank" rel="noopener" :style="{ pointerEvents: built.xlsx ? 'auto' : 'none', opacity: built.xlsx ? 1 : 0.5 }">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          {{ built.xlsx ? '下载 Excel' : '尚未生成' }}
        </a>
      </div>
      <div class="export-card" :class="{ empty: !built.ppt }">
        <div class="logo" style="background:linear-gradient(135deg,#f59e0b,#ef4444)">PPT</div>
        <h3>PPT 周报</h3>
        <p>基于模板 · 采购表格自动分页 · 9 + 9' 双页</p>
        <a class="btn btn-primary dl-btn" :href="pptHref()" target="_blank" rel="noopener" :style="{ pointerEvents: built.ppt ? 'auto' : 'none', opacity: built.ppt ? 1 : 0.5 }">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          {{ built.ppt ? '下载 PPT' : '尚未生成' }}
        </a>
      </div>
      <div class="export-card" :class="{ empty: !(built.xlsx && built.ppt) }">
        <div class="logo" style="background:linear-gradient(135deg,#6366f1,#8b5cf6)">ZIP</div>
        <h3>整周打包</h3>
        <p>Excel + PPT + png 图文件夹 一次性下载</p>
        <a class="btn btn-secondary dl-btn" :href="bundleHref()" target="_blank" rel="noopener" :style="{ pointerEvents: (built.xlsx && built.ppt) ? 'auto' : 'none', opacity: (built.xlsx && built.ppt) ? 1 : 0.5 }">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 16h-6a8 8 0 0 1-7-7V3a5 5 0 0 0-3.39 8.39"/></svg>
          下载 {{ weekId }}-bundle.zip
        </a>
      </div>
    </div>

    <div class="alert alert-info">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
      <div>
        所有产物保存于 <code class="mono">output/{{ weekId }}/</code>。
        重新上传同一周的 Excel 会<b>覆盖数据但保留工作内容 + AI 文案</b>(用 week_id 主键关联)。
      </div>
    </div>
  </div>

  <div class="continue-bar">
    <div class="hint">完成 · 一键打包可发给老板 / 团队。</div>
    <button class="btn btn-secondary" @click="gotoStep(3)">返回 预览</button>
    <button class="btn btn-primary" @click="startOver">开始下一周</button>
  </div>
</template>

<style scoped>
.kpi .kpi-val { transition: font-size 0.2s; }
</style>
