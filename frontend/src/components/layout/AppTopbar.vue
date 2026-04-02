<template>
  <header class="topbar">
    <slot />
  </header>
</template>

<script setup lang="ts">
</script>

<style scoped>
.topbar {
  height: 48px;
  min-height: 48px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  padding: 0 1rem;
}
</style>
