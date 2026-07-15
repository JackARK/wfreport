<script setup>
import { ref, inject, computed } from 'vue'
import { aiSection, generate } from '../api'

const props = defineProps({ weekId: String })
const showToast = inject('showToast')

const busyAI = ref({ wc: false, ds: false, proc: false, plan: false })
const aiText = ref({ wc: '', ds: '' })
const procInput = ref(''); const planInput = ref('')
const procItems = ref([]); const planItems = ref([])

const links = ref(null)
const generating = ref(false)
const genErr = ref('')

async function genAI(kind, section) {
  if (!props.weekId) { showToast?.('请先上传当周数据', 'error'); return }
  busyAI.value[kind] = true
  try {
    const r = await aiSection(section, kind === 'proc' ? { input: procInput.value } : kind === 'plan' ? { input: planInput.value } : { week_id: props.weekId })
    if (kind === 'wc' || kind === 'ds') {
      aiText.value[kind] = r.data.text || ''
      showToast?.('文案已生成 · 可在下方修改', 'success')
    } else if (kind === 'proc') {
      procItems.value = r.data.items || []
      showToast?.(`已结构化 ${procItems.value.length} 条采购要点`, 'success')
    } else if (kind === 'plan') {
      planItems.value = r.data.items || []
      showToast?.(`已结构化 ${planItems.value.length} 条下周计划`, 'success')
    }
  } catch (err) {
    showToast?.('AI 调用失败: ' + (err?.response?.data?.detail || err.message), 'error')
  } finally {
    busyAI.value[kind] = false
  }
}

function addProc() { procItems.value.push({ 事项内容: '', '进度及责任人': [], 状态: '待处理', 完成时间: '' }) }
function addPlan() { planItems.value.push({ 事项内容: '', 提出时间: '', 次周预计完成节点名称: '', 涉及部门: '' }) }
function rmProc(i) { procItems.value.splice(i, 1) }
function rmPlan(i) { planItems.value.splice(i, 1) }
function addOwner(i) { procItems.value[i]['进度及责任人'].push('') }

async function doGenerate() {
  if (!props.weekId) { showToast?.('请先上传当周数据', 'error'); return }
  generating.value = true; genErr.value = ''; links.value = null
  try {
    const r = await generate(props.weekId, {
      ai_texts: { week_compare: aiText.value.wc, daily_summary: aiText.value.ds, procurement: '', next_plan: '' },
      procurement_items: procItems.value,
      plan_items: planItems.value,
      narratives: { brand: '', brand_share: '', product: '', new: '' },
    })
    links.value = r.data
    showToast?.('Excel + PPT 已生成', 'success')
  } catch (err) {
    genErr.value = err?.response?.data?.detail || err.message || '生成失败'
  } finally {
    generating.value = false
  }
}

const canGen = computed(() => !!props.weekId)
</script>

<template>
  <div class="page-head">
    <div>
      <h2>生成周报<span v-if="weekId" class="muted mono" style="font-size:14px;font-weight:500;margin-left:8px">{{ weekId }}</span></h2>
      <p>用 AI 生成文案 + 润色采购与计划 · 一键产出 Excel + PPT</p>
    </div>
  </div>

  <div v-if="!weekId" class="card">
    <div class="empty">
      <div class="emoji">🧾</div>
      <h3>还没有数据</h3>
      <p>请先在「上传」页导入本周销售明细 Excel。</p>
    </div>
  </div>

  <template v-else>
    <div class="split mb-6">
      <div class="card">
        <div class="card-head">
          <div>
            <h3>① 上周对比</h3>
            <div class="desc">AI 基于本周 vs 上周核心指标生成</div>
          </div>
          <button class="btn btn-primary btn-sm" @click="genAI('wc', 'week_compare')" :disabled="busyAI.wc">
            <span v-if="busyAI.wc" class="spinner"/> 生成文案
          </button>
        </div>
        <div class="card-body">
          <textarea class="textarea" rows="5" v-model="aiText.wc" placeholder="点击「生成文案」或直接输入…"/>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <div>
            <h3>② 每日总结</h3>
            <div class="desc">基于每日金额与加权毛利率</div>
          </div>
          <button class="btn btn-primary btn-sm" @click="genAI('ds', 'daily_summary')" :disabled="busyAI.ds">
            <span v-if="busyAI.ds" class="spinner"/> 生成文案
          </button>
        </div>
        <div class="card-body">
          <textarea class="textarea" rows="5" v-model="aiText.ds" placeholder="点击「生成文案」或直接输入…"/>
        </div>
      </div>
    </div>

    <div class="split mb-6">
      <div class="card">
        <div class="card-head">
          <div>
            <h3>③ 采购要点</h3>
            <div class="desc">输入要点 → AI 结构化为表格</div>
          </div>
          <button class="btn btn-primary btn-sm" @click="genAI('proc', 'procurement')" :disabled="busyAI.proc || !procInput.trim()">
            <span v-if="busyAI.proc" class="spinner"/> AI 结构化
          </button>
        </div>
        <div class="card-body">
          <label class="field"><span>采购要点 (要点输入)</span><textarea class="textarea" rows="3" v-model="procInput" placeholder="例:A 产品下周到货 / B 工厂欠料催交…"/></label>
          <div v-if="procItems.length" class="tbl-wrap">
            <table class="tbl">
              <thead><tr><th style="width:32px">#</th><th>事项内容</th><th>进度 & 责任人</th><th style="width:110px">状态</th><th style="width:120px">完成时间</th><th style="width:36px"/></tr></thead>
              <tbody>
                <tr v-for="(it, i) in procItems" :key="i">
                  <td>{{ i + 1 }}</td>
                  <td><input class="input" v-model="it.事项内容"/></td>
                  <td>
                    <div v-for="(_, k) in it['进度及责任人']" :key="k" class="flex items-center gap-2 mb-2">
                      <input class="input" v-model="it['进度及责任人'][k]"/>
                      <button class="btn btn-ghost btn-sm" @click="it['进度及责任人'].splice(k,1)">×</button>
                    </div>
                    <button class="btn btn-ghost btn-sm" @click="addOwner(i)">+ 责任人</button>
                  </td>
                  <td><input class="input" v-model="it.状态"/></td>
                  <td><input class="input" v-model="it.完成时间" placeholder="YYYY-MM-DD"/></td>
                  <td><button class="btn btn-ghost btn-sm" @click="rmProc(i)">×</button></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="mt-3"><button class="btn btn-secondary btn-sm" @click="addProc">+ 新增一行</button></div>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <div>
            <h3>④ 下周计划</h3>
            <div class="desc">输入要点 → AI 结构化为表格</div>
          </div>
          <button class="btn btn-primary btn-sm" @click="genAI('plan', 'next_plan')" :disabled="busyAI.plan || !planInput.trim()">
            <span v-if="busyAI.plan" class="spinner"/> AI 结构化
          </button>
        </div>
        <div class="card-body">
          <label class="field"><span>下周计划 (要点输入)</span><textarea class="textarea" rows="3" v-model="planInput" placeholder="例:C 品牌新品上架 / 系统对接联调…"/></label>
          <div v-if="planItems.length" class="tbl-wrap">
            <table class="tbl">
              <thead><tr><th style="width:32px">#</th><th>事项内容</th><th style="width:120px">提出时间</th><th>次周预计完成节点</th><th style="width:120px">涉及部门</th><th style="width:36px"/></tr></thead>
              <tbody>
                <tr v-for="(it, i) in planItems" :key="i">
                  <td>{{ i + 1 }}</td>
                  <td><input class="input" v-model="it.事项内容"/></td>
                  <td><input class="input" v-model="it.提出时间"/></td>
                  <td><input class="input" v-model="it.次周预计完成节点名称"/></td>
                  <td><input class="input" v-model="it.涉及部门"/></td>
                  <td><button class="btn btn-ghost btn-sm" @click="rmPlan(i)">×</button></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="mt-3"><button class="btn btn-secondary btn-sm" @click="addPlan">+ 新增一行</button></div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <h3>⑤ 一键生成</h3>
          <div class="desc">产出 Excel (多 sheet + 原生图表) 与 PPT (基于模板)</div>
        </div>
      </div>
      <div class="card-body">
        <div v-if="genErr" class="alert alert-danger mb-3">{{ genErr }}</div>
        <button class="btn btn-primary btn-lg" :disabled="!canGen || generating" @click="doGenerate">
          <span v-if="generating" class="spinner"/> 一键生成 Excel + PPT
        </button>
        <div v-if="links" class="mt-4">
          <div class="charts-grid">
            <a class="card" style="text-decoration:none;color:inherit" :href="'http://localhost:8000' + links.excel" target="_blank" rel="noopener">
              <div class="card-body flex items-center gap-3">
                <div class="brand-logo" style="background:linear-gradient(135deg,#10b981,#06b6d4)">XLS</div>
                <div style="flex:1">
                  <div style="font-weight:600">下载 Excel</div>
                  <div class="muted" style="font-size:12.5px">含多 sheet + 原生图表</div>
                </div>
                <span class="chip">下载 ↓</span>
              </div>
            </a>
            <a class="card" style="text-decoration:none;color:inherit" :href="'http://localhost:8000' + links.ppt" target="_blank" rel="noopener">
              <div class="card-body flex items-center gap-3">
                <div class="brand-logo" style="background:linear-gradient(135deg,#f59e0b,#ef4444)">PPT</div>
                <div style="flex:1">
                  <div style="font-weight:600">下载 PPT</div>
                  <div class="muted" style="font-size:12.5px">基于模板 · 采购自动分页</div>
                </div>
                <span class="chip">下载 ↓</span>
              </div>
            </a>
          </div>
        </div>
      </div>
    </div>
  </template>
</template>
