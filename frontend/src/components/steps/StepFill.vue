<script setup>
import { ref, watch, onMounted, inject } from 'vue'
import { aiSection, getWorkspace, putWorkspace } from '../../api'
import { workspace, setPlanItems, setProcurementItems, setContent, gotoStep, markStepDone } from '../../store'

const showToast = inject('showToast')
const props = defineProps({ weekId: String })

const sub = ref('plan')  // 'plan' | 'content'  (采购 vs 本周/下周)

const tabLocal = ref('content')
watch(() => props.weekId, async (w) => {
  if (!w) return
  try {
    const r = await getWorkspace(w)
    if (Array.isArray(r.workspace.plan_items))    setPlanItems(r.workspace.plan_items)
    if (Array.isArray(r.workspace.procurement_items)) setProcurementItems(r.workspace.procurement_items)
    setContent(r.workspace.content || '')
  } catch (e) { /* empty workspace is fine */ }
}, { immediate: true })

// ---- AI state ----
const aiLoading = ref({ wc: false, ds: false, proc: false, plan: false })
async function gen(kind) {
  const map = {
    wc:   { section: 'week_compare', toast: '上周对比文案' },
    ds:   { section: 'daily_summary', toast: '每日总结文案' },
    proc: { section: 'procurement',   toast: '采购要点' },
    plan: { section: 'next_plan',     toast: '下周计划' },
  }
  const cfg = map[kind]
  if ((kind === 'proc' || kind === 'plan') && !workspace.content) {
    showToast?.('请先在「本周内容」写一些要点', 'error'); return
  }
  aiLoading.value[kind] = true
  try {
    const r = await aiSection(cfg.section, kind === 'wc' || kind === 'ds'
      ? { week_id: props.weekId }
      : { input: workspace.content })
    if (kind === 'wc' || kind === 'ds') {
      workspace.aiTexts[kind === 'wc' ? 'week_compare' : 'daily_summary'] = r.data.text || ''
      showToast?.(`${cfg.toast}已生成`, 'success')
    } else if (kind === 'proc') {
      setProcurementItems(r.data.items || [])
      showToast?.(`已结构化 ${workspace.procurementItems.length} 条采购`, 'success')
    } else if (kind === 'plan') {
      setPlanItems(r.data.items || [])
      showToast?.(`已结构化 ${workspace.planItems.length} 条下周计划`, 'success')
    }
    save()
  } catch (err) {
    showToast?.('AI 调用失败: ' + (err?.response?.data?.detail || err.message), 'error')
  } finally {
    aiLoading.value[kind] = false
  }
}

// ---- autosave (debounced) ----
let saveTimer = null
function scheduleSave() {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(save, 800)
}
async function save() {
  if (!props.weekId) return
  try {
    await putWorkspace(props.weekId, {
      content: workspace.content,
      plan_items: workspace.planItems,
      procurement_items: workspace.procurementItems,
    })
  } catch (e) { /* swallow - next save will retry */ }
}
watch(() => workspace.content, () => scheduleSave())
watch(() => workspace.planItems, () => scheduleSave(), { deep: true })
watch(() => workspace.procurementItems, () => scheduleSave(), { deep: true })

// ---- content (本周工作笔记) ----
const charCount = ref(0)
watch(() => workspace.content, (v) => { charCount.value = (v || '').length }, { immediate: true })

// ---- table row helpers ----
function addProc() {
  setProcurementItems([...workspace.procurementItems, { 事项内容: '', '进度及责任人': [''], 状态: '待处理', 完成时间: '' }])
}
function addPlan() {
  setPlanItems([...workspace.planItems, { 事项内容: '', 提出时间: '', 次周预计完成节点名称: '', 涉及部门: '' }])
}
function rmProc(i) {
  const a = [...workspace.procurementItems]; a.splice(i, 1); setProcurementItems(a)
}
function rmPlan(i) {
  const a = [...workspace.planItems]; a.splice(i, 1); setPlanItems(a)
}
function addOwner(i) {
  const a = [...workspace.procurementItems]
  a[i]['进度及责任人'] = [...(a[i]['进度及责任人'] || []), '']
  setProcurementItems(a)
}
function rmOwner(i, j) {
  const a = [...workspace.procurementItems]
  a[i]['进度及责任人'].splice(j, 1)
  setProcurementItems(a)
}

function canForward() {
  return workspace.planItems.length > 0 || workspace.procurementItems.length > 0 || (workspace.content && workspace.content.trim().length > 0)
}

function goForward() {
  if (!canForward()) { showToast?.('请至少在任意一项填入内容', 'error'); return }
  save()
  markStepDone(2); gotoStep(3)
}
</script>

<template>
  <div class="step-head">
    <div class="badge">2</div>
    <div>
      <h2>填写本周内容与下周规划</h2>
      <p>自由记录要点 · AI 帮你润色/分条 · 系统自动保存到 SQLite</p>
    </div>
    <div class="right">
      <span class="chip" style="background:var(--success-soft);color:var(--success)">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
        自动保存
      </span>
    </div>
  </div>

  <div style="padding: 0 32px">
    <div class="card mb-4">
      <div class="card-head">
        <div>
          <h3>本周内容 & 下周规划</h3>
          <div class="desc">左:本周工作要点(自由文本 + AI 结构化) 右:下周计划(可编辑表格 + AI 结构化)</div>
        </div>
        <div class="flex gap-2">
          <button class="btn btn-secondary btn-sm" :class="{ on: tabLocal==='content' }" @click="tabLocal='content'">本周要点</button>
          <button class="btn btn-secondary btn-sm" :class="{ on: tabLocal==='plan' }" @click="tabLocal='plan'">下周计划表</button>
        </div>
      </div>
      <div class="card-body" v-if="tabLocal==='content'">
        <label class="field">
          <span class="flex items-center justify-between">
            <span>本周工作要点 (自由记录)</span>
            <span class="muted" style="font-size:11.5px">{{ charCount }} 字</span>
          </span>
          <textarea
            class="textarea"
            rows="8"
            v-model="workspace.content"
            placeholder="例: A 产品本周促销活动效果超预期 / B 渠道库存周转改善 / C 工厂交期准时率提升 ... 自由写,AI 会自动帮你润色 + 结构化"
          />
        </label>
      </div>
      <div class="card-body" v-else>
        <div class="flex items-center gap-2 mb-3">
          <button class="btn btn-secondary btn-sm" @click="gen('plan')" :disabled="aiLoading.plan || !workspace.content">
            <span v-if="aiLoading.plan" class="spinner"/>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
            AI 结构化下周计划
          </button>
          <span class="muted" style="font-size:11.5px">基于上方本周要点自动拆条</span>
        </div>
        <div class="table-editor" v-if="workspace.planItems.length">
          <div class="th fill-grid-plan">
            <div>#</div><div>事项内容</div><div>提出时间</div><div>次周预计完成节点</div><div>涉及部门</div><div></div>
          </div>
          <div class="row fill-grid-plan" v-for="(it, i) in workspace.planItems" :key="i">
            <div class="muted mono">{{ i + 1 }}</div>
            <input class="input-cell" v-model="it.事项内容" placeholder="事项内容"/>
            <input class="input-cell" v-model="it.提出时间" placeholder="YYYY-MM-DD"/>
            <input class="input-cell" v-model="it.次周预计完成节点名称" placeholder="节点名称"/>
            <input class="input-cell" v-model="it.涉及部门" placeholder="部门"/>
            <button class="btn btn-ghost btn-sm" @click="rmPlan(i)" aria-label="删除">×</button>
          </div>
        </div>
        <button class="btn btn-secondary btn-sm add-row-btn" @click="addPlan">+ 新增一行</button>
      </div>
    </div>

    <div class="fill-cols">
      <!-- 本周采购 -->
      <div class="card">
        <div class="card-head">
          <div>
            <h3>本周采购要点</h3>
            <div class="desc">已完成的采购跟进 · 含责任人与节点</div>
          </div>
          <button class="btn btn-secondary btn-sm" @click="gen('proc')" :disabled="aiLoading.proc || !workspace.content">
            <span v-if="aiLoading.proc" class="spinner"/>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
            AI 结构化
          </button>
        </div>
        <div class="table-editor" v-if="workspace.procurementItems.length">
          <div class="th fill-grid-proc">
            <div>#</div><div>事项内容</div><div>进度 & 责任人</div><div>状态</div><div>完成时间</div><div></div>
          </div>
          <div class="row fill-grid-proc" v-for="(it, i) in workspace.procurementItems" :key="i">
            <div class="muted mono">{{ i + 1 }}</div>
            <input class="input-cell" v-model="it.事项内容" placeholder="事项内容"/>
            <div class="row-owners">
              <div class="owner-row" v-for="(_, k) in it['进度及责任人']" :key="k">
                <input class="input-cell" v-model="it['进度及责任人'][k]" placeholder="进度 / 责任人"/>
                <button class="btn btn-ghost btn-sm" @click="rmOwner(i, k)">×</button>
              </div>
              <button class="btn btn-ghost btn-sm" @click="addOwner(i)">+ 责任人</button>
            </div>
            <input class="input-cell" v-model="it.状态" placeholder="状态"/>
            <input class="input-cell" v-model="it.完成时间" placeholder="YYYY-MM-DD"/>
            <button class="btn btn-ghost btn-sm" @click="rmProc(i)" aria-label="删除">×</button>
          </div>
        </div>
        <button class="btn btn-secondary btn-sm add-row-btn" @click="addProc">+ 新增一行</button>
      </div>

      <!-- 下周计划 表格视图 -->
      <div class="card">
        <div class="card-head">
          <div>
            <h3>下周计划</h3>
            <div class="desc">可直接编辑,或切到上方标签页用 AI 一键结构化</div>
          </div>
          <button class="btn btn-secondary btn-sm" @click="gen('plan')" :disabled="aiLoading.plan || !workspace.content">
            <span v-if="aiLoading.plan" class="spinner"/>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
            AI 结构化
          </button>
        </div>
        <div class="table-editor" v-if="workspace.planItems.length">
          <div class="th fill-grid-plan">
            <div>#</div><div>事项内容</div><div>提出时间</div><div>次周预计完成节点</div><div>涉及部门</div><div></div>
          </div>
          <div class="row fill-grid-plan" v-for="(it, i) in workspace.planItems" :key="i">
            <div class="muted mono">{{ i + 1 }}</div>
            <input class="input-cell" v-model="it.事项内容" placeholder="事项内容"/>
            <input class="input-cell" v-model="it.提出时间" placeholder="YYYY-MM-DD"/>
            <input class="input-cell" v-model="it.次周预计完成节点名称" placeholder="节点名称"/>
            <input class="input-cell" v-model="it.涉及部门" placeholder="部门"/>
            <button class="btn btn-ghost btn-sm" @click="rmPlan(i)" aria-label="删除">×</button>
          </div>
        </div>
        <button class="btn btn-secondary btn-sm add-row-btn" @click="addPlan">+ 新增一行</button>
      </div>
    </div>
  </div>

  <div class="continue-bar">
    <div class="hint">
      <template v-if="canForward()">
        已填写 <b>{{ workspace.planItems.length }}</b> 条下周计划 · <b>{{ workspace.procurementItems.length }}</b> 条采购要点 · 可进入预览。
      </template>
      <template v-else>
        请至少在一处填写内容,才能进入预览。可以是工作要点、采购行或计划行中的任意一项。
      </template>
    </div>
    <button class="btn btn-secondary" @click="gotoStep(1)">返回 上传</button>
    <button class="btn btn-primary btn-lg" :disabled="!canForward()" @click="goForward">
      下一步: 生成预览
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-left:6px"><polyline points="9 18 15 12 9 6"/></svg>
    </button>
  </div>
</template>

<style scoped>
.btn.on { background: var(--primary-soft); color: var(--primary); border-color: var(--primary-soft); }
</style>
