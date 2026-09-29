<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { DIRECTION_OPTIONS, directionLabel } from '../direction'
const trips = ref<any[]>([])
const events = ref<any[]>([])
onMounted(async () => {
  trips.value = await api('/trips')
  try {
    events.value = (await api('/reports/run?line_id=1', { method: 'POST' })).events || []
  } catch { events.value = [] }
})
async function changeDirection(t: any, e: Event) {
  const direction = (e.target as HTMLSelectElement).value
  const updated = await api(`/trips/${t.id}`, { method: 'PATCH', body: JSON.stringify({ direction }) })
  Object.assign(t, updated)
}
function stripClass(s: string) {
  return s === 'bunching' ? 'bg-bunch' : s === 'large_gap' ? 'bg-large' : ''
}
function label(s: string) {
  return s === 'bunching' ? '串车' : s === 'large_gap' ? '大间隔' : '正常'
}
</script>
<template>
  <h1>班次 · 间隔条带</h1>
  <p class="sub">左侧班次清单（可改方向），右侧串车/间隔竖直条带</p>
  <div class="bg-split">
    <aside class="bg-trip-col">
      <h2>班次列表</h2>
      <div v-for="r in trips" :key="r.id ?? r.trip_no" class="bg-trip-row">
        <div>
          <div>{{ r.trip_no }}</div>
          <div class="bg-trip-meta">线路 {{ r.line_id }} · 车 {{ r.vehicle_no }}</div>
        </div>
        <div class="bg-trip-side">
          <select class="dir-select" :value="r.direction" @change="changeDirection(r, $event)">
            <option v-for="o in DIRECTION_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
          </select>
          <div class="bg-trip-meta">{{ r.planned_depart }}</div>
        </div>
      </div>
    </aside>
    <div class="bg-strip-col">
      <article
        v-for="(e, i) in events"
        :key="i"
        class="bg-gap-strip"
        :class="stripClass(e.status)"
      >
        <header>{{ e.stop_name }} · {{ directionLabel(e.direction) }}</header>
        <div class="bg-gap-body">
          <div class="bg-gap-val">{{ e.gap_min }}′</div>
          <div>计划 {{ e.planned_headway_min }}′</div>
          <div>{{ e.earlier_trip }} → {{ e.later_trip }}</div>
          <span class="badge" :class="e.status === 'bunching' ? 'badge-bad' : e.status === 'large_gap' ? 'badge-warn' : 'badge-ok'">
            {{ label(e.status) }}
          </span>
        </div>
      </article>
      <p v-if="!events.length" class="muted">暂无间隔事件</p>
    </div>
  </div>
</template>
