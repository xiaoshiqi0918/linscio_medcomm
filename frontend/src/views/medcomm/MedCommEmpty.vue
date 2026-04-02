<template>
  <div class="medcomm-empty">
    <el-empty description="选择左侧文章或点击右上角「+ 新建」开始创作">
      <el-button type="primary" @click="goNew">+ 新建文章</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

const router = useRouter()
const route = useRoute()

async function goNew() {
  if (route.name === 'medcomm-new') {
    await router.replace({ path: '/medcomm/new', query: { t: String(Date.now()) } })
    return
  }
  await router.push('/medcomm/new')
}
</script>

<style scoped>
.medcomm-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: #fafafa;
}
</style>
