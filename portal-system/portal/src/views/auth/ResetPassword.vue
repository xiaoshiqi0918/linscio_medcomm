<template>
  <div class="auth-page">
    <div class="auth-card card">
      <h1 class="auth-title">重置密码</h1>
      <p class="auth-subtitle text-muted">该功能暂未开放，请联系客服重置密码。</p>
      <div class="auth-links mt-2">
        <router-link to="/login">返回登录</router-link>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.auth-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px; }
.auth-card { width: 100%; max-width: 420px; }
.auth-title { font-size: 24px; font-weight: 600; margin-bottom: 4px; }
.auth-subtitle { margin-bottom: 24px; }
.auth-links { font-size: 13px; }
</style>
