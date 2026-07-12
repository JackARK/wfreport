<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'; import Plotly from 'plotly.js-dist-min'; import { preview } from '../api'
const props = defineProps(['weekId']); const data = ref(null)
async function load(){ if(!props.weekId) return; const r = await preview(props.weekId); data.value = r.data; await nextTick(); renderAll() }
function renderAll(){
  if(!data.value) return
  for(const [k,fig] of Object.entries(data.value.figures)){
    const el = document.getElementById('fig-'+k); if(el) Plotly.newPlot(el, fig)
  }
}
onMounted(load); watch(()=>props.weekId, load)
</script>
<template>
  <div v-if="data">
    <h2>预览 {{ props.weekId }}</h2>
    <div v-for="(_,k) in data.figures" :key="k"><h3>{{ k }}</h3><div :id="'fig-'+k" style="width:100%;height:480px"></div></div>
  </div>
  <div v-else>请先上传</div>
</template>
