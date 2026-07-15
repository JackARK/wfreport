<script setup>
import { STEP_META, stepState, gotoStep } from '../store'

defineProps({ compact: Boolean })
</script>

<template>
  <div class="wf-steps" :class="{ compact }">
    <template v-for="(s, i) in STEP_META" :key="s.id">
      <button
        class="wf-step"
        :class="stepState(s.id)"
        :disabled="stepState(s.id) === 'pending'"
        @click="stepState(s.id) !== 'pending' && gotoStep(s.id)"
      >
        <span class="wf-bullet">
          <svg v-if="stepState(s.id) === 'done'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          <template v-else>{{ s.id }}</template>
        </span>
        <div>
          <div class="wf-label">{{ s.title }}</div>
          <div v-if="!compact" class="wf-meta">{{ s.desc }}</div>
        </div>
      </button>
      <div v-if="i < STEP_META.length - 1" class="wf-connector" :class="stepState(s.id+1) === 'done' || stepState(s.id+1) === 'current' ? 'wf-done' : ''"/>
    </template>
  </div>
</template>
