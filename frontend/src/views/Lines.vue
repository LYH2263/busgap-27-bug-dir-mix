<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { DIRECTION_OPTIONS } from '../direction'
const rows = ref<any[]>([])
onMounted(async () => { rows.value = await api('/lines') })
async function changeDirection(r: any, e: Event) {
  const direction = (e.target as HTMLSelectElement).value
  const updated = await api(`/lines/${r.id}`, { method: 'PATCH', body: JSON.stringify({ direction }) })
  Object.assign(r, updated)
}
</script>
<template>
  <h1>线路</h1>
  <p class="sub">运营线路与串车 / 大间隔判定阈值 · 可修改线路默认方向</p>
  <p class="muted">业务页与检测读口未强制同参与集</p>
  <div class="card">
    <table>
      <thead><tr><th>编码</th><th>名称</th><th>方向</th><th>计划间隔(分)</th><th>串车阈值</th><th>大间隔阈值</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)">
          <td>{{ r.code }}</td><td>{{ r.name }}</td>
          <td>
            <select class="dir-select" :value="r.direction" @change="changeDirection(r, $event)">
              <option v-for="o in DIRECTION_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
          </td>
          <td>{{ r.planned_headway_min }}</td><td>{{ r.bunch_threshold }}</td><td>{{ r.large_threshold }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
