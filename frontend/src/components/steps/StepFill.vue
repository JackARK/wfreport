<script setup>
import { ref, computed, watch, onMounted, inject } from 'vue'
import { parseWorkspace, putWorkspace } from '../../api'
import { workspace, setContent, setPlanText, setPlanItems, setProcurementItems,
         gotoStep, markStepDone, resetWorkspace, scheduleAutosave } from '../../store'

const emit = defineEmits([])
const showToast = inject('showToast')
const props = defineProps({ weekId: String })

const tab = ref('thisWeek')   // 'thisWeek' | 'nextWeek'

const aiBusy = ref(false)
const showStructured = ref(false)
const lastParsedAt = ref(null)   // last successful parse

function save() {
  if (!props.weekId) return
  return putWorkspace(props.weekId, {
    content: workspace.content,
    plan_text: workspace.planText,
    plan_items: workspace.planItems,
    procurement_items: workspace.procurementItems,
  }).catch(() => { /* swallow */ })
}
watch(() => workspace.content, () => scheduleAutosave(save))
watch(() => workspace.planText, () => scheduleAutosave(save))
watch(() => workspace.planItems, () => scheduleAutosave(save), { deep: true })
watch(() => workspace.procurementItems, () => scheduleAutosave(save), { deep: true })

// ---- AI parse ----
async function aiParse() {
  if (!props.weekId) { showToast?.('请先上传数据', 'error'); return }
  if (!workspace.content.trim() && !workspace.planText.trim()) {
    showToast?.('请先在两个文本框写一点内容', 'error'); return
  }
  aiBusy.value = true
  try {
    const r = await parseWorkspace(props.weekId, {
      content: workspace.content,
      plan_text: workspace.planText,
    })
    if (Array.isArray(r.workspace?.procurement_items)) setProcurementItems(r.workspace.procurement_items)
    if (Array.isArray(r.workspace?.plan_items))        setPlanItems(r.workspace.plan_items)
    lastParsedAt.value = new Date()
    const procN = r.workspace?.procurement_items?.length || 0
    const planN = r.workspace?.plan_items?.length || 0
    if (procN + planN === 0) {
      showToast?.('AI 没抽出结构化条目 · 内容可能太简洁或缺细节 · 可手动在下面加', 'error')
    } else {
      showToast?.(`AI 已整理 · 采购 ${procN} 条 · 下周计划 ${planN} 条`, 'success')
    }
    showStructured.value = true
  } catch (err) {
    showToast?.('AI 解析失败: ' + (err?.response?.data?.detail || err.message), 'error')
  } finally {
    aiBusy.value = false
  }
}

function addProc() {
  setProcurementItems([...workspace.procurementItems, { 事项内容: '', '进度及责任人': [''], 状态: '待处理', 完成时间: '' }])
}
function rmProc(i) {
  const a = [...workspace.procurementItems]; a.splice(i, 1); setProcurementItems(a)
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
function addPlan() {
  setPlanItems([...workspace.planItems, { 事项内容: '', 提出时间: '', 次周预计完成节点名称: '', 涉及部门: '' }])
}
function rmPlan(i) {
  const a = [...workspace.planItems]; a.splice(i, 1); setPlanItems(a)
}

const hasAnyData = computed(() => {
  return workspace.content.trim().length > 0
    || workspace.planText.trim().length > 0
    || workspace.planItems.length > 0
    || workspace.procurementItems.length > 0
})
const hasParsedItems = computed(() => workspace.planItems.length > 0 || workspace.procurementItems.length > 0)

function canForward() {
  // Need at least one of: freeform text or AI-parsed items
  return hasAnyData.value
}

function goForward() {
  if (!canForward()) { showToast?.('请填写本周内容或下周计划', 'error'); return }
  // ensure latest is saved
  save()
  markStepDone(2)
  gotoStep(3)
}

function restartFromScratch() {
  if (!confirm('重新开始会清空整个工作流 · 回到第 1 步上传。\n\n确定?')) return
  resetWorkspace()
  gotoStep(1)
  showToast?.('已重新开始 · 回到第 1 步', 'info')
}

function loadSample() {
  if (workspace.content || workspace.planText) {
    if (!confirm('将覆盖已填写的内容,确认?')) return
  }
  workspace.content =
`【销售侧】
1. 抖音-初医生家居旗舰店完成 A 产品上新,日均销售 +18%,爬坡符合预期
2. 拼多多-猫人家纺 通过价格策略调整,库存周转天数从 38 → 26
3. 淘宝天猫-初医生旗舰店 客服首响从 90s 压到 45s,带动转化 +0.6pp
4. 抖音-初医生家居用品 主图点击率掉到 4.2%,下周做主图 A/B

【商品 + 采购跟进】
1. 工厂 B 欠料拖了 2 周,周三终于出货,这次降一档工厂评级
2. 工厂 C 首批大货质检 3% 不合格,已返工,质量协议要重签
3. 新品「拼色多功能趴睡带头枕」用户测试 OK,可以正式上线`
  workspace.planText =
`【商品 · 周二前】
- 海马抱枕系列完成图文拍摄并上架 (运营 + 设计)
- 猫人家纺 库存补货到货 2000 件,周三全部入仓 (仓储)
- 拼多多猫人店铺仓库盘点校正,涉及 SKU 38 个 (仓储 + 运营)

【流量】
- 抖音-初医生家居主图 A/B 测试,出 2-3 个方向 (运营 + 设计)
- 淘宝直通车人群包重设,剔除近 14 天未点击 (运营)

【技术 · 周五联调/上线】
- 退款流程与订单系统实时同步 (技术 - 周三联调)
- 库存预警阈值 + 飞书机器人告警 (技术 - 周五上线)`
  setContent(workspace.content)
  setPlanText(workspace.planText)
}

function fmtAgo(d) {
  if (!d) return ''
  const s = Math.floor((Date.now() - d.getTime()) / 1000)
  if (s < 60) return s + ' 秒前'
  if (s < 3600) return Math.floor(s / 60) + ' 分钟前'
  return Math.floor(s / 3600) + ' 小时前'
}
const now = ref(Date.now())
setInterval(() => { now.value = Date.now() }, 30000)
const parsedAgo = computed(() => fmtAgo(lastParsedAt.value))
</script>

<template>
  <div class="step-head">
    <div class="badge">2</div>
    <div>
      <h2>填写本周内容与下周规划</h2>
      <p>两段自然语言记录 → 一键 AI 拆条 → 自动生成 Excel / PPT</p>
    </div>
    <div class="right">
      <span v-if="lastParsedAt" class="chip" style="background:var(--success-soft);color:var(--success)">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
        {{ parsedAgo }}已解析
      </span>
    </div>
  </div>

  <div style="padding: 0 32px">
    <div class="card mb-4">
      <div class="card-head">
        <div>
          <h3>本周内容 & 下周规划</h3>
          <div class="desc">
            <span>左:本周做了什么(含采购跟进) · </span>
            <span>右:下周重点(含责任部门)</span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button class="btn btn-secondary btn-sm" @click="tab='thisWeek'" :class="{ on: tab==='thisWeek' }">本周</button>
          <button class="btn btn-secondary btn-sm" @click="tab='nextWeek'" :class="{ on: tab==='nextWeek' }">下周</button>
          <button class="btn btn-ghost btn-sm" @click="loadSample">载入示例</button>
        </div>
      </div>
      <div class="card-body">
        <label class="field" v-if="tab==='thisWeek'">
          <span class="flex items-center justify-between">
            <span>本周工作要点 (自由记录,含采购跟进)</span>
            <span class="muted" style="font-size:11.5px">{{ workspace.content.length }} 字 · 自动保存</span>
          </span>
          <textarea
            class="textarea"
            rows="10"
            :value="workspace.content"
            @input="(e) => setContent(e.target.value)"
            placeholder="例: 抖音 -初医生家居完成 A 产品上新,日均 +18%; 工厂 B 欠料催交完成; 客服首响从 90s 压到 45s ... 自由写,AI 会自动拆成结构化表格"
          />
        </label>
        <label class="field" v-else>
          <span class="flex items-center justify-between">
            <span>下周工作计划 (自由记录,含目标 / 节点 / 责任部门)</span>
            <span class="muted" style="font-size:11.5px">{{ workspace.planText.length }} 字 · 自动保存</span>
          </span>
          <textarea
            class="textarea"
            rows="10"
            :value="workspace.planText"
            @input="(e) => setPlanText(e.target.value)"
            placeholder="例: 商品 -海马抱枕系列 完成图文拍摄, 周二前 (运营 + 设计); 流量 -主图 A/B 测试 (运营 + 设计); 技术 -退款流程实时同步, 周五联调 ..."
          />
        </label>

        <div class="flex items-center gap-2 mt-3">
          <button class="btn btn-primary btn-lg" @click="aiParse" :disabled="aiBusy">
            <span v-if="aiBusy" class="spinner"/>
            <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
            <span v-if="aiBusy">解析中 ...</span>
            <span v-else>📝→📊 AI 解析并保存</span>
          </button>
          <span class="muted" style="font-size:12px">
            {{ workspace.planItems.length + workspace.procurementItems.length }} 条已结构化
          </span>
          <button v-if="hasParsedItems" class="btn btn-ghost btn-sm" @click="showStructured = !showStructured">
            {{ showStructured ? '收起' : '查看' }} AI 抽出的条目
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" :style="{ transform: showStructured ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }"><polyline points="6 9 12 15 18 9"/></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- AI-parsed structured rows (collapsible) -->
    <div v-if="showStructured && hasParsedItems" class="fill-cols">
      <div class="card">
        <div class="card-head">
          <div>
            <h3>采购跟进 · AI 抽出的 {{ workspace.procurementItems.length }} 条</h3>
            <div class="desc">直接编辑 · 自动保存 · 嵌入 Excel 采购表</div>
          </div>
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
            <button class="btn btn-ghost btn-sm" @click="rmProc(i)">×</button>
          </div>
        </div>
        <button class="btn btn-secondary btn-sm add-row-btn" @click="addProc">+ 新增一行</button>
      </div>

      <div class="card">
        <div class="card-head">
          <div>
            <h3>下周计划 · AI 抽出的 {{ workspace.planItems.length }} 条</h3>
            <div class="desc">直接编辑 · 自动保存 · 嵌入 Excel + PPT</div>
          </div>
        </div>
        <div class="table-editor" v-if="workspace.planItems.length">
          <div class="th fill-grid-plan">
            <div>#</div><div>事项内容</div><div>提出时间</div><div>次周节点</div><div>涉及部门</div><div></div>
          </div>
          <div class="row fill-grid-plan" v-for="(it, i) in workspace.planItems" :key="i">
            <div class="muted mono">{{ i + 1 }}</div>
            <input class="input-cell" v-model="it.事项内容" placeholder="事项内容"/>
            <input class="input-cell" v-model="it.提出时间" placeholder="YYYY-MM-DD"/>
            <input class="input-cell" v-model="it.次周预计完成节点名称" placeholder="节点"/>
            <input class="input-cell" v-model="it.涉及部门" placeholder="部门"/>
            <button class="btn btn-ghost btn-sm" @click="rmPlan(i)">×</button>
          </div>
        </div>
        <button class="btn btn-secondary btn-sm add-row-btn" @click="addPlan">+ 新增一行</button>
      </div>
    </div>

    <div v-if="!hasAnyData" class="alert alert-info mt-3">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
      <div>
        在左侧两个文本框任意一个中写要点。AI 会自动拆成采购 / 下周计划两条结构化表格。<b>无需手动逐行填写。</b>
      </div>
    </div>
  </div>

  <div class="continue-bar">
    <div class="hint">
      <template v-if="canForward()">
        已填写 <b>{{ workspace.content.length + workspace.planText.length }}</b> 字 · <b>{{ workspace.planItems.length + workspace.procurementItems.length }}</b> 条结构化 · 可进入预览
      </template>
      <template v-else>
        请先在「本周」或「下周」标签页写一点要点 · AI 会自动补全
      </template>
    </div>
    <button class="btn btn-ghost" @click="restartFromScratch" title="清空整个工作流并回到第 1 步">↻ 重新开始</button>
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
