<script setup>
import { ref, watch, onMounted, nextTick, inject } from 'vue'
import Plotly from 'plotly.js-dist-min'
import { getWorkspace, aiSection, putWorkspace } from '../../api'
import { workspace, setAiTexts, setNarrativeOverride, gotoStep, markStepDone, resetWorkspace } from '../../store'

const showToast = inject('showToast')
const props = defineProps({ weekId: String })

const data = ref(null)
const loading = ref(false)
const aiBusy = ref({ wc: false, ds: false })

async function load() {
  if (!props.weekId) return
  loading.value = true
  try {
    const r = await getWorkspace(props.weekId)
    data.value = r.data || r  // tolerate both with/without wrapper
  } catch (e) {
    showToast?.('预览加载失败: ' + (e.message || ''), 'error')
  } finally {
    loading.value = false
  }
}
watch(() => props.weekId, load, { immediate: true })

onMounted(load)

async function renderAll() {
  if (!data.value || !data.value.figures) return
  await nextTick()
  for (const [k, fig] of Object.entries(data.value.figures)) {
    const el = document.getElementById('fig-' + k)
    if (el) {
      try {
        Plotly.newPlot(el, fig.data, fig.layout, { displaylogo: false, responsive: true, locale: 'zh-CN' })
      } catch (e) {}
    }
  }
}
watch(data, () => setTimeout(renderAll, 50), { flush: 'post' })

async function genAI(kind) {
  if (!props.weekId) return
  aiBusy.value[kind] = true
  try {
    const r = await aiSection(kind === 'wc' ? 'week_compare' : 'daily_summary', { week_id: props.weekId })
    const text = r.data.text || ''
    setAiTexts({ [kind === 'wc' ? 'week_compare' : 'daily_summary']: text })
    const label = kind === 'wc' ? '上周对比' : '每日总结'
    if (text.length > 0) {
      showToast?.(`${label}文案已生成 · 共 ${text.length} 字`, 'success')
    } else {
      showToast?.(`${label}生成结果为空 · 请检查 AI 配置或手动填写`, 'error')
    }
    saveNarratives()
  } catch (e) {
    showToast?.('AI 调用失败: ' + (e?.response?.data?.detail || e.message || ''), 'error')
  } finally {
    aiBusy.value[kind] = false
  }
}

function onWcInput(e) {
  setAiTexts({ week_compare: e.target.value })
  saveNarratives()
}
function onDsInput(e) {
  setAiTexts({ daily_summary: e.target.value })
  saveNarratives()
}

let debounceSave = null
function saveNarratives() {
  clearTimeout(debounceSave)
  debounceSave = setTimeout(async () => {
    if (!props.weekId) return
    try {
      await putWorkspace(props.weekId, { narrative_overrides: workspace.narrativeOverrides })
    } catch {}
  }, 600)
}

function fmtMoney(n) { return '¥ ' + Number(n || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function fmtNum(n)   { return Number(n || 0).toLocaleString('zh-CN') }
function fmtPct(n)   { return (Number(n || 0) * 100).toFixed(2) + '%' }

function goForward() { markStepDone(3); gotoStep(4) }

function restartFromScratch() {
  if (!confirm('重新开始会清空整个工作流 (上传数据 + 工作内容 + 计划 + AI 文案) · 回到第 1 步上传。\n\n确定?')) return
  resetWorkspace()
  gotoStep(1)
  showToast?.('已重新开始 · 回到第 1 步', 'info')
}
</script>

<template>
  <div class="step-head">
    <div class="badge">3</div>
    <div>
      <h2>周报预览</h2>
      <p>下面是本周周报的完整预览,包含 4 个核心 KPI、11 张图表、AI 文案与表格。可随时回到上一步修改。</p>
    </div>
    <div class="right">
      <span class="chip">{{ data?.overview ? '已就绪' : '加载中…' }}</span>
    </div>
  </div>

  <div style="padding: 0 32px">
    <template v-if="!data">
      <div class="charts-grid" style="margin-top:8px">
        <div v-for="i in 4" :key="i" class="kpi">
          <div class="skel" style="height:14px;width:60%"/>
          <div class="skel mt-3" style="height:26px;width:80%"/>
        </div>
      </div>
      <div class="charts-grid mt-6">
        <div v-for="i in 4" :key="i" class="card chart-card">
          <div class="card-head"><div class="skel" style="height:18px;width:140px"/></div>
          <div class="card-body"><div class="skel" style="height:300px"/></div>
        </div>
      </div>
    </template>

    <template v-else-if="data.overview">
      <!-- KPI strip -->
      <div class="preview-mini-grid mb-4">
        <div class="preview-mini">
          <div class="lbl">销售金额</div>
          <div class="val">{{ fmtMoney(data.overview.销售金额) }}</div>
          <div class="sub">本周累计 · Σ销售金额</div>
        </div>
        <div class="preview-mini">
          <div class="lbl">销售毛利</div>
          <div class="val">{{ fmtMoney(data.overview.销售毛利) }}</div>
          <div class="sub">本周累计 · Σ销售毛利</div>
        </div>
        <div class="preview-mini">
          <div class="lbl">毛利率 (加权)</div>
          <div class="val" style="color:var(--primary)">{{ fmtPct(data.overview.销售毛利率) }}</div>
          <div class="sub">Σ毛利 ÷ Σ金额 · 行级不平均</div>
        </div>
        <div class="preview-mini">
          <div class="lbl">销售数量</div>
          <div class="val">{{ fmtNum(data.overview.销售数量) }}</div>
          <div class="sub">本周累计 · 件</div>
        </div>
      </div>

      <!-- AI Narrative: editable -->
      <div class="card mb-4">
        <div class="card-head">
          <div>
            <h3>AI 文案 (可编辑)</h3>
            <div class="desc">点击空白处直接编辑 · 修改会保存到后端并覆盖默认生成</div>
          </div>
          <div class="flex gap-2">
            <button class="btn btn-secondary btn-sm" @click="genAI('wc')" :disabled="aiBusy.wc">
              <span v-if="aiBusy.wc" class="spinner"/>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
              重新生成 · 上周对比
            </button>
            <button class="btn btn-secondary btn-sm" @click="genAI('ds')" :disabled="aiBusy.ds">
              <span v-if="aiBusy.ds" class="spinner"/>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
              重新生成 · 每日总结
            </button>
          </div>
        </div>
        <div class="card-body">
          <div class="row-2">
            <div>
              <label class="field">
                <span>① 上周对比 · 本周 vs 上周</span>
                <textarea
                  class="textarea"
                  rows="6"
                  :value="workspace.aiTexts.week_compare"
                  @input="onWcInput"
                  placeholder="点击「重新生成 · 上周对比」生成文案,或直接键入..."
                />
                <span v-if="workspace.aiTexts.week_compare" class="muted" style="font-size:11.5px">
                  共 <b>{{ workspace.aiTexts.week_compare.length }}</b> 字 · 已自动保存
                </span>
              </label>
            </div>
            <div>
              <label class="field">
                <span>② 每日总结</span>
                <textarea
                  class="textarea"
                  rows="6"
                  :value="workspace.aiTexts.daily_summary"
                  @input="onDsInput"
                  placeholder="点击「重新生成 · 每日总结」生成文案,或直接键入..."
                />
                <span v-if="workspace.aiTexts.daily_summary" class="muted" style="font-size:11.5px">
                  共 <b>{{ workspace.aiTexts.daily_summary.length }}</b> 字 · 已自动保存
                </span>
              </label>
            </div>
          </div>
          <div class="alert alert-info mt-3">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
            <div>上方是 <b>本周内容</b> + <b>AI 生成的对比与总结</b>。所有修改已自动保存,导出时会原样带入 Excel + PPT。</div>
          </div>
        </div>
      </div>

      <!-- 表格摘要 -->
      <div v-if="data.tables" class="card mb-4">
        <div class="card-head">
          <div>
            <h3>本周要点摘要</h3>
            <div class="desc">采购 {{ workspace.procurementItems.length }} 条 · 下周计划 {{ workspace.planItems.length }} 条 · 品牌 {{ data.tables.brand?.length || 0 }} 个</div>
          </div>
        </div>
        <div class="card-body">
          <div v-if="workspace.procurementItems.length" class="mb-4">
            <h4 style="margin:0 0 8px;font-size:13px;color:var(--text-muted)">采购跟进 ({{ workspace.procurementItems.length }})</h4>
            <div class="tbl-wrap"><table class="tbl">
              <thead><tr><th>事项内容</th><th>状态</th><th>完成时间</th></tr></thead>
              <tbody>
                <tr v-for="(it, i) in workspace.procurementItems" :key="i">
                  <td>{{ it.事项内容 || '—' }}</td>
                  <td>{{ it.状态 || '—' }}</td>
                  <td>{{ it.完成时间 || '—' }}</td>
                </tr>
              </tbody>
            </table></div>
          </div>
          <div v-if="workspace.planItems.length">
            <h4 style="margin:0 0 8px;font-size:13px;color:var(--text-muted)">下周计划 ({{ workspace.planItems.length }})</h4>
            <div class="tbl-wrap"><table class="tbl">
              <thead><tr><th>事项内容</th><th>涉及部门</th><th>完成节点</th></tr></thead>
              <tbody>
                <tr v-for="(it, i) in workspace.planItems" :key="i">
                  <td>{{ it.事项内容 || '—' }}</td>
                  <td>{{ it.涉及部门 || '—' }}</td>
                  <td>{{ it.次周预计完成节点名称 || '—' }}</td>
                </tr>
              </tbody>
            </table></div>
          </div>
        </div>
      </div>

      <!-- 11 张图 缩略 -->
      <div class="charts-grid">
        <div class="card chart-card" v-for="(f, i) in [
          { key: 'overview', title: '汇总概览' },
          { key: 'daily', title: '每日趋势' },
          { key: 'brand_combo', title: '品牌销售' },
          { key: 'brand_pie', title: '品牌占比' },
          { key: 'platform', title: '平台销售' },
          { key: 'shop_heatmap', title: '店铺 TOP15' },
          { key: 'product_horizontal', title: '产品 TOP15' },
          { key: 'product_table', title: '产品 TOP15 明细' },
          { key: 'product_heatmap', title: '产品热力 TOP15' },
          { key: 'new_products', title: '新品表现' },
          { key: 'three_weeks', title: '近三周对比' },
          { key: 'factory', title: '工厂 TOP5' },
        ]" :key="f.key">
          <div class="card-head">
            <h3 style="font-size:13.5px">{{ f.title }}</h3>
          </div>
          <div class="card-body"><div :id="'fig-' + f.key" class="plot"/></div>
        </div>
      </div>
    </template>
  </div>

  <div class="continue-bar">
    <div class="hint">预览就绪。下一步将渲染 Excel + PPT 并打包下载。</div>
    <button class="btn btn-ghost" @click="restartFromScratch" title="清空整个工作流并回到第 1 步">↻ 重新开始</button>
    <button class="btn btn-secondary" @click="gotoStep(2)">返回 填写</button>
    <button class="btn btn-primary btn-lg" @click="goForward">
      下一步: 导出下载
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-left:6px"><polyline points="9 18 15 12 9 6"/></svg>
    </button>
  </div>
</template>

<style scoped>
.plot { width: 100%; height: 300px; }
</style>
