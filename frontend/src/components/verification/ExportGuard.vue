<template>
  <div v-if="show" class="export-guard">
    <el-alert type="info" :closable="false" show-icon>
      <template #title>导出前检查（防编造四道防线）</template>
      导出时将自动检测数据占位符、绝对化表述；若有未处理警告需您确认后再导出。
    </el-alert>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  show?: boolean
}>()
</script>

<style scoped>
.export-guard { margin-bottom: 0.5rem; }
</style>
