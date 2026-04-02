<template>
  <div class="home">
    <h1>LinScio MedComm</h1>
    <p class="subtitle">医学科普写作智能体</p>
    <el-space wrap>
      <el-button type="primary" @click="$router.push('/medcomm')">进入科普写作</el-button>
      <el-button @click="$router.push('/settings')">设置</el-button>
    </el-space>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  gap: 1rem;
}

h1 {
  font-size: 2rem;
  color: #1a1a2e;
}

.subtitle {
  color: #666;
  margin-bottom: 1rem;
}
</style>
