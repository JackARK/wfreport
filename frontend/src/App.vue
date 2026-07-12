<script setup>
import { ref } from 'vue'
import UploadPage from './components/UploadPage.vue'
import PreviewPage from './components/PreviewPage.vue'
import ConfigPage from './components/ConfigPage.vue'
import GeneratePage from './components/GeneratePage.vue'
const tab = ref('upload')
const weekId = ref('')
</script>
<template>
  <div>
    <nav>
      <button :class="{on:tab==='upload'}" @click="tab='upload'">上传</button>
      <button :class="{on:tab==='preview'}" @click="tab='preview'">预览</button>
      <button :class="{on:tab==='config'}" @click="tab='config'">配置</button>
      <button :class="{on:tab==='generate'}" @click="tab='generate'">生成</button>
    </nav>
    <UploadPage v-if="tab==='upload'" @done="(w)=>{weekId=w; tab='preview'}"/>
    <PreviewPage v-if="tab==='preview'" :weekId="weekId"/>
    <ConfigPage v-if="tab==='config'"/>
    <GeneratePage v-if="tab==='generate'" :weekId="weekId"/>
  </div>
</template>
