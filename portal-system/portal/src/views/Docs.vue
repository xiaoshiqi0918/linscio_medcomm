<template>
  <div class="docs-v6 page-shell">
    <section class="hero section-hero">
      <div class="hero-bg">
        <div class="grid"></div>
        <div class="orb orb-a"></div>
        <div class="orb orb-b"></div>
      </div>
      <div class="container container-shell">
        <div class="tag tag-pill">DOCUMENTATION</div>
        <h1>LinScio AI 文档中心</h1>
        <p class="sub">安装步骤、系统架构、功能说明与部署指南。以下入口与你当前门户和项目文档体系保持一致。</p>

        <div class="entry-grid">
          <article class="entry-card reveal">
            <h3>门户使用文档</h3>
            <p>面向门户用户：注册、激活、用户中心、机器管理与下载使用说明。</p>
            <a href="/docs/" target="_blank" rel="noopener noreferrer" class="btn btn-base btn-primary-ui">前往 /docs/</a>
          </article>
          <article class="entry-card reveal">
            <h3>部署与运维文档</h3>
            <p>腾讯云/宝塔部署、端口规划、反向代理、升级与故障排查。</p>
            <router-link to="/download" class="btn btn-base btn-outline-ui">前往下载与部署入口</router-link>
          </article>
          <article class="entry-card reveal">
            <h3>API 与接口约定</h3>
            <p>查看后端 OpenAPI 与客户端对接接口（登录后可使用完整能力）。</p>
            <a href="/api/docs" target="_blank" rel="noopener noreferrer" class="btn btn-base btn-outline-ui">前往 API Docs</a>
          </article>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="container container-shell content-grid">
        <article id="intro" class="block card-base reveal">
          <h2>系统简介</h2>
          <p><strong>LinScio AI（聆思恪）</strong>是面向学术领域的 AI 智能体应用集群，在用户本机部署。品牌内核：聆你所需，思你所问，恪守专业边界。</p>
          <ul>
            <li><strong>33 个 AI 智能体</strong>：四层架构（编排层、阶段智能体、通用智能体、工具层），由工作流引擎统一调度。</li>
            <li><strong>5 大业务模块</strong>：文献管理、论文写作、科普创作、数据分析、质控工具。</li>
            <li><strong>本地优先</strong>：数据默认存储在用户本地，可选对接云端 API 与本地 Ollama。</li>
          </ul>
        </article>

        <article id="install" class="block card-base reveal">
          <h2>下载与安装</h2>
          <p><strong>Step 1</strong> 注册并激活：在门户注册/登录后输入授权码激活。</p>
          <p><strong>Step 2</strong> 获取安装包：进入下载页获取服务端部署包或客户端包。</p>
          <p><strong>Step 3</strong> 启动使用：按文档部署后访问对应地址开始使用。</p>
          <div class="actions">
            <router-link to="/auth" class="btn btn-base btn-primary-ui">去注册 / 登录</router-link>
            <router-link to="/download" class="btn btn-base btn-outline-ui">前往下载页</router-link>
          </div>
        </article>

        <article id="tech" class="block card-base reveal">
          <h2>技术栈与数据持久化</h2>
          <p><strong>技术栈</strong>：后端 FastAPI，前端 Vue 3 + Vite，数据库 PostgreSQL + pgvector。</p>
          <p><strong>数据落盘</strong>：数据库、文件、日志与配置均支持本地或私有部署路径管理。</p>
          <p>完整技术细节请在部署文档与 API 文档中查看。</p>
        </article>

        <article id="more" class="block card-base reveal">
          <h2>更多文档入口</h2>
          <ul>
            <li><a href="/docs/" target="_blank" rel="noopener noreferrer">门户帮助文档（/docs/）</a></li>
            <li><a href="/api/docs" target="_blank" rel="noopener noreferrer">API 文档（/api/docs）</a></li>
            <li><router-link to="/download">下载中心（客户端与服务端部署包）</router-link></li>
          </ul>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const io = ref(null)

onMounted(() => {
  io.value = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible')
        io.value?.unobserve(entry.target)
      }
    })
  }, { threshold: 0.12 })
  document.querySelectorAll('.reveal').forEach((el) => io.value?.observe(el))
})

onBeforeUnmount(() => {
  io.value?.disconnect()
})
</script>

<style scoped>
.docs-v6 { background: var(--color-bg-base); }
.container { max-width: var(--container-max); margin: 0 auto; padding: 0 var(--space-6); }

.hero { position: relative; padding: 54px 0 28px; overflow: hidden; border-bottom: 1px solid var(--color-border-soft); background: linear-gradient(160deg, #f0f7ff 0%, #e8f2ff 40%, #f5f9ff 70%, #ffffff 100%); }
.hero-bg { position: absolute; inset: 0; }
.grid { position: absolute; inset: 0; background-image: linear-gradient(#dbeafe 1px, transparent 1px), linear-gradient(90deg, #dbeafe 1px, transparent 1px); background-size: 54px 54px; opacity: .35; }
.orb { position: absolute; border-radius: 50%; filter: blur(95px); }
.orb-a { width: 420px; height: 420px; top: -120px; right: -130px; background: rgba(59,130,246,.22); }
.orb-b { width: 320px; height: 320px; bottom: -140px; left: -90px; background: rgba(45,212,191,.16); }
.hero .container { position: relative; z-index: 2; }

.hero h1 { margin: 14px 0 10px; font-size: clamp(30px, 4vw, 46px); color: var(--color-text-strong); }
.sub { color: var(--color-text-muted); max-width: 860px; line-height: 1.7; }

.entry-grid { margin-top: 18px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.entry-card {
  background: var(--color-bg-base);
  border: 1.5px solid var(--color-border-soft);
  border-radius: 14px;
  padding: 16px;
  transition: all .25s ease;
}
.entry-card:hover {
  border-color: var(--color-border-brand);
  box-shadow: var(--shadow-card);
}
.entry-card h3 { margin-bottom: 8px; font-size: 18px; color: var(--color-text-strong); }
.entry-card p { color: var(--color-text-muted); line-height: 1.7; margin-bottom: 10px; font-size: var(--fs-md); }

.section { padding: 30px 0 50px; background: var(--color-bg-soft); }
.content-grid { display: grid; gap: 14px; }
.block { padding: 22px; transition: all .25s ease; }
.block:hover {
  border-color: var(--color-border-brand);
  box-shadow: var(--shadow-card-hover);
}
.block h2 { margin-bottom: 10px; font-size: var(--fs-2xl); color: var(--color-text-strong); }
.block p { color: var(--color-text-body); line-height: 1.75; margin-bottom: 10px; }
.block ul { margin: 0; padding-left: 18px; color: var(--color-text-muted); display: grid; gap: 6px; line-height: 1.7; }
.block a { color: var(--color-brand-700); text-decoration: none; }
.block a:hover { color: var(--color-brand-600); }
.actions { margin-top: 12px; display: flex; gap: 10px; flex-wrap: wrap; }

.btn { text-decoration: none; }

.reveal { opacity: 0; transform: translateY(18px); transition: all .5s ease; }
.reveal.visible { opacity: 1; transform: translateY(0); }

@media (max-width: 980px) {
  .entry-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 640px) {
  .entry-grid { grid-template-columns: 1fr; }
}
</style>
