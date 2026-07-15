<script setup>
import { ref, onMounted, inject } from 'vue'
import { getPrompts, putPrompts } from '../api'

const showToast = inject('showToast')

const tpl = ref({})
const loading = ref(false)
const saving  = ref(false)
const dirty   = ref(false)
const initial = ref({})

const META = {
  week_compare:  { label: '上周对比',  desc: '生成「本周 vs 上周」环比段落' },
  daily_summary: { label: '每日总结',  desc: '生成每日销售趋势分点总结' },
  procurement:   { label: '采购要点',  desc: '润色 + 分条 + 结构化为表格行' },
  next_plan:     { label: '下周计划',  desc: '润色 + 分条 + 结构化为表格行' },
}

onMounted(async () => {
  loading.value = true
  try {
    const r = await getPrompts()
    tpl.value = r.data
    initial.value = JSON.parse(JSON.stringify(r.data))
    dirty.value = false
  } catch (err) {
    showToast?.('加载 prompt 失败', 'error')
  } finally {
    loading.value = false
  }
})

function markDirty() { dirty.value = true }

async function save() {
  saving.value = true
  try {
    await putPrompts(tpl.value)
    initial.value = JSON.parse(JSON.stringify(tpl.value))
    dirty.value = false
    showToast?.('已保存并热加载到后端', 'success')
  } catch (err) {
    showToast?.('保存失败: ' + (err.message || ''), 'error')
  } finally {
    saving.value = false
  }
}

async function revert() {
  tpl.value = JSON.parse(JSON.stringify(initial.value))
  dirty.value = false
  showToast?.('已撤销修改', 'info')
}
</script>

<template>
  <div class="page-head">
    <div>
      <h2>AI Prompt 模板</h2>
      <p>编辑后保存即生效 (热加载) · 无需重启后端 · 模板使用 Jinja2 变量语法 <code class="mono">双花括号</code></p>
    </div>
    <div class="flex items-center gap-2">
      <span v-if="dirty" class="chip" style="background:#fef3c7;color:#92400e">● 有未保存的改动</span>
      <button class="btn btn-secondary" :disabled="!dirty || saving" @click="revert">撤销</button>
      <button class="btn btn-primary" :disabled="!dirty || saving" @click="save">
        <span v-if="saving" class="spinner"/> 保存并热生效
      </button>
    </div>
  </div>

  <div v-if="loading" class="charts-grid">
    <div v-for="i in 4" :key="i" class="card">
      <div class="card-body"><div class="skel" style="height:200px"/></div>
    </div>
  </div>

  <div v-else class="charts-grid">
    <div v-for="(section, key) in tpl" :key="key" class="card">
      <div class="card-head">
        <div>
          <h3>{{ META[key]?.label || key }}</h3>
          <div class="desc">{{ META[key]?.desc }}</div>
        </div>
        <span class="chip mono">{{ key }}</span>
      </div>
      <div class="card-body">
        <label class="field">
          <span>系统提示</span>
          <textarea class="textarea" rows="3" v-model="section.system" @input="markDirty"/>
        </label>
        <label class="field" style="margin-bottom:0">
          <span>用户提示 (模板)</span>
          <textarea class="textarea" rows="8" v-model="section.user" @input="markDirty"/>
        </label>
      </div>
    </div>
  </div>
</template>
