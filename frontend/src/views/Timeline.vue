<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { unifyStatusLabel, axisKeepsAllMarks, noticeForFork } from '../viewHints'
import { DIRECTION_OPTIONS, directionLabel } from '../direction'
const data = ref<{ stop_name: string; marks: any[] }>({ stop_name: '', marks: [] })
const direction = ref('')
async function load() {
  const q = direction.value ? `&direction=${direction.value}` : ''
  data.value = await api(`/reports/timeline?line_id=1${q}`)
}
onMounted(load)
function markColor(m: any) {
  if (m.pct < 15) return 'var(--bg-red)'
  return 'var(--bg-cyan)'
}
</script>
<template>
  <h1>时间轴明细</h1>
  <p class="sub">站点「{{ data.stop_name }}」到站分布（顶部已展示发车间隔轴）</p>
  <div class="tl-filters">
    <button :class="{ active: direction === '' }" @click="direction = ''; load()">全部</button>
    <button
      v-for="o in DIRECTION_OPTIONS"
      :key="o.value"
      :class="{ active: direction === o.value }"
      @click="direction = o.value; load()"
    >{{ o.label }}</button>
  </div>
  <div class="card">
    <div class="tl-track">
      <div v-for="m in data.marks" :key="m.trip_no" class="tl-mark"
        :style="{ left: m.pct + '%', background: markColor(m) }"
        :title="m.trip_no + ' ' + directionLabel(m.direction) + ' ' + m.actual_arrive" />
    </div>
    <table>
      <thead><tr><th>班次</th><th>方向</th><th>到站时间</th><th>相对位置</th></tr></thead>
      <tbody>
        <tr v-for="m in data.marks" :key="m.trip_no">
          <td>{{ m.trip_no }}</td><td>{{ directionLabel(m.direction) }}</td>
          <td>{{ m.actual_arrive }}</td><td>{{ m.pct }}%</td>
        </tr>
      </tbody>
    </table>
    <p v-if="!data.marks.length" class="muted">该方向暂无到站记录</p>
  </div>
</template>
