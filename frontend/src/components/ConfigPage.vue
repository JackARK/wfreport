<script setup>
import { ref, onMounted } from 'vue'; import { getPrompts, putPrompts } from '../api'
const tpl = ref({}); const out = ref('')
onMounted(async()=> tpl.value = (await getPrompts()).data)
async function save(){ out.value = JSON.stringify((await putPrompts(tpl.value)).data) }
</script>
<template>
  <div><h2>Prompt 模板配置</h2>
    <div v-for="(v,k) in tpl" :key="k">
      <h3>{{ k }}</h3>
      <textarea v-model="v.user" rows="6" style="width:100%"></textarea>
    </div>
    <button @click="save">保存</button><pre>{{ out }}</pre>
  </div>
</template>
