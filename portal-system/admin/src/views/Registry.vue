<template>
  <div class="registry-page">
    <h2>镜像版本</h2>
    <el-card>
      <p>镜像仓库由 Docker Registry 提供，可通过 Registry Web UI 查看仓库与标签列表。</p>
      <el-descriptions :column="1" border class="mt">
        <el-descriptions-item label="Registry 地址">registry.linscio.com.cn（生产环境请以实际域名为准）</el-descriptions-item>
        <el-descriptions-item label="Web UI">hub.linscio.com.cn — 管理员可在此查看镜像列表、标签及删除镜像</el-descriptions-item>
      </el-descriptions>
      <p class="tip mt">若需在本后台直接展示镜像版本列表，可后续对接 Registry V2 API（/v2/_catalog、/v2/&lt;name&gt;/tags/list）。</p>
    </el-card>
  </div>
</template>

<script setup>
</script>

<style scoped>
.registry-page { padding: 0 0 24px 0; }
.mt { margin-top: 16px; }
.tip { font-size: 13px; color: #666; }
</style>
