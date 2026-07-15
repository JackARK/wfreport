<script setup>
import { ref, watch, onMounted, inject } from 'vue'
import Plotly from 'plotly.js-dist-min'
import { preview } from '../api'

const props = defineProps({ weekId: String })
const showToast = inject('showToast')

const data = ref(null)
const loading = ref(false)
const errMsg = ref('')

const figures = [
  { key: 'overview',        title: '汇总概览',   desc: '本周核心数字',     kind: 'chart' },
  { key: 'daily',           title: '每日趋势',   desc: '日销售额与日销售数量', kind: 'chart' },
  { key: 'brand_combo',     title: '品牌销售',   desc: '销售额与毛利率',     kind: 'chart' },
  { key: 'brand_pie',       title: '品牌占比',   desc: '销售数量占比',       kind: 'chart' },
  { key: 'platform',        title: '平台销售',   desc: '各平台金额与数量',   kind: 'chart' },
  { key: 'shop_heatmap',    title: '店铺热力 TOP15', desc: '日 × 店铺 销售数量', kind: 'chart' },
  { key: 'product_combo',   title: '产品 TOP15', desc: '销售数量TOP15',     kind: 'chart' },
  { key: 'product_heatmap', title: '产品热力 TOP15', desc: '日 × 产品 销售数量', kind: 'chart' },
  { key: 'new_products',    title: '新品表现',   desc: '本周新品指标',       kind: 'chart' },
  { key: 'three_weeks',     title: '近三周对比', desc: '跨周趋势表',         kind: 'table' },
  { key: 'factory',         title: '工厂 TOP5',  desc: '工厂交付表现',       kind: 'table' },
]

async function load() {
  if (!props.weekId) return
  loading.value = true; errMsg.value = ''
  try {
    const r = await preview(props.weekId)
    data.value = r.data
    await new Promise(r => requestAnimationFrame(r))
    renderAll()
  } catch (err) {
    errMsg.value = err?.response?.data?.detail || err.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function renderAll() {
  if (!data.value) return
  for (const [k, fig] of Object.entries(data.value.figures)) {
    const el = document.getElementById('fig-' + k)
    if (!el) continue
    Plotly.newPlot(el, fig.data, fig.layout, {
      displaylogo: false,
      responsive: true,
      locale: 'zh-CN',
    })
  }
}

onMounted(load)
watch(() => props.weekId, load)

function fmtMoney(n) { return '¥ ' + Number(n || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function fmtNum(n)   { return Number(n || 0).toLocaleString('zh-CN') }
function fmtPct(n)  { return (Number(n || 0) * 100).toFixed(2) + '%' }
</script>

<template>
  <div class="page-head">
    <div>
      <h2>本周预览<span v-if="weekId" class="muted mono" style="font-size:14px;font-weight:500;margin-left:8px">{{ weekId }}</span></h2>
      <p>所有汇总指标按加权法计算 · Σ销售毛利 / Σ销售金额 · 行级毛利率不平均</p>
    </div>
  </div>

  <div v-if="!weekId" class="card">
    <div class="empty">
      <div class="emoji">📊</div>
      <h3>还没有数据</h3>
      <p>请先在「上传」页导入本周销售明细 Excel。</p>
    </div>
  </div>

  <template v-else-if="loading && !data">
    <div class="kpi-grid">
      <div v-for="i in 4" :key="i" class="kpi">
        <div class="skel" style="height:14px;width:60%"/>
        <div class="skel mt-3" style="height:26px;width:80%"/>
      </div>
    </div>
    <div class="charts-grid">
      <div v-for="i in 4" :key="i" class="card chart-card">
        <div class="card-head"><div class="skel" style="height:18px;width:140px"/></div>
        <div class="card-body"><div class="skel" style="height:300px"/></div>
      </div>
    </div>
  </template>

  <template v-else-if="errMsg">
    <div class="alert alert-danger">{{ errMsg }}</div>
  </template>

  <template v-else-if="data">
    <div class="kpi-grid">
      <div class="kpi acc-1">
        <div class="kpi-label">销售金额</div>
        <div class="kpi-val">{{ fmtMoney(data.overview.销售金额) }}</div>
        <div class="kpi-foot">本周累计</div>
      </div>
      <div class="kpi acc-2">
        <div class="kpi-label">销售毛利</div>
        <div class="kpi-val">{{ fmtMoney(data.overview.销售毛利) }}</div>
        <div class="kpi-foot">本周累计</div>
      </div>
      <div class="kpi acc-3">
        <div class="kpi-label">毛利率 (加权)</div>
        <div class="kpi-val">{{ fmtPct(data.overview.销售毛利率) }}</div>
        <div class="kpi-foot">Σ毛利 ÷ Σ金额</div>
      </div>
      <div class="kpi acc-4">
        <div class="kpi-label">销售数量</div>
        <div class="kpi-val">{{ fmtNum(data.overview.销售数量) }}</div>
        <div class="kpi-foot">本周累计</div>
      </div>
    </div>

    <div class="charts-grid">
      <template v-for="f in figures" :key="f.key">
        <div class="card chart-card">
          <div class="card-head">
            <div>
              <h3>{{ f.title }}</h3>
              <div class="desc">{{ f.desc }}</div>
            </div>
            <span class="chip">{{ f.kind === 'table' ? '表格' : '图表' }}</span>
          </div>
          <div class="card-body">
            <div :id="'fig-' + f.key" class="plot"/>
          </div>
        </div>
      </template>
    </div>

    <div class="card mt-6">
      <div class="card-head">
        <div>
          <h3>明细表 · 品牌</h3>
          <div class="desc">按金额降序 · 数量占比 = 品牌数量 ÷ 总量</div>
        </div>
      </div>
      <div class="tbl-wrap" style="border:none;border-radius:0">
        <table class="tbl">
          <thead>
            <tr><th>品牌</th><th>销售金额</th><th>销售数量</th><th>销售毛利</th><th>毛利率</th><th>数量占比</th></tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in data.tables.brand" :key="i">
              <td>{{ r.品牌 }}</td>
              <td>{{ fmtMoney(r.销售金额) }}</td>
              <td>{{ fmtNum(r.销售数量) }}</td>
              <td>{{ fmtMoney(r.销售毛利) }}</td>
              <td>{{ fmtPct(r.销售毛利率) }}</td>
              <td>{{ fmtPct(r.数量占比) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </template>
</template>
