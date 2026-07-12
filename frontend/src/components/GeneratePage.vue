<script setup>
import { ref } from 'vue'; import { aiSection, generate, dl } from '../api'
const props = defineProps(['weekId'])
const wc = ref(''), ds = ref(''), proc = ref(''), plan = ref(''), links = ref(null)
const procIn = ref(''), planIn = ref('')
async function genWC(){ wc.value = (await aiSection('week_compare',{vars:{}})).data.text }
async function genDaily(){ ds.value = (await aiSection('daily_summary',{vars:{}})).data.text }
async function genProc(){ proc.value = JSON.stringify((await aiSection('procurement',{input:procIn.value})).data.items) }
async function genPlan(){ plan.value = JSON.stringify((await aiSection('next_plan',{input:planIn.value})).data.items) }
async function doGenerate(){
  const r = await generate(props.weekId, {
    ai_texts:{week_compare:wc.value, daily_summary:ds.value, procurement:'', next_plan:''},
    procurement_items: JSON.parse(proc.value||'[]'), plan_items: JSON.parse(plan.value||'[]'),
    narratives:{brand:'',brand_share:'',product:'',new:''}
  }); links.value = r.data
}
</script>
<template>
  <div><h2>生成 {{ props.weekId }}</h2>
    <button @click="genWC">生成上周对比</button><pre>{{ wc }}</pre>
    <button @click="genDaily">生成每日总结</button><pre>{{ ds }}</pre>
    <h3>采购</h3><textarea v-model="procIn" rows="3" style="width:100%"></textarea><button @click="genProc">AI 润色</button><pre>{{ proc }}</pre>
    <h3>下周计划</h3><textarea v-model="planIn" rows="3" style="width:100%"></textarea><button @click="genPlan">AI 润色</button><pre>{{ plan }}</pre>
    <button @click="doGenerate">一键生成 Excel+PPT</button>
    <div v-if="links"><a :href="'http://localhost:8000' + links.excel">下载Excel</a> <a :href="'http://localhost:8000' + links.ppt">下载PPT</a></div>
  </div>
</template>
