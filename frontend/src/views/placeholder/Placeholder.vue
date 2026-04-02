<template>
  <div class="placeholder">
    <el-empty :description="`${title} - 开发中`">
      <template #image>
        <span class="emoji">🚧</span>
      </template>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => (route.meta?.title as string) || '此功能')
</script>

<style scoped>
.placeholder {
  padding: 3rem;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}

.emoji {
  font-size: 4rem;
}
</style>
