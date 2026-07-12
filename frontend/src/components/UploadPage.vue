<script setup>
import { ref } from 'vue'; import { upload } from '../api'
const emit = defineEmits(['done']); const msg = ref(''); const file = ref(null)
async function onUpload(){
  if(!file.value){ msg.value='请选择文件'; return }
  const r = await upload(file.value); msg.value = JSON.stringify(r.data); emit('done', r.data.week_id)
}
</script>
<template>
  <div><h2>上传本周 Excel</h2>
    <input type="file" @change="e=>file=e.target.files[0]" accept=".xlsx"/>
    <button @click="onUpload">上传</button><pre>{{ msg }}</pre>
  </div>
</template>
