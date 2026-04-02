<template>
  <div class="about-v7">
    <section class="hero">
      <div class="hero-bg">
        <div class="grid"></div>
        <div class="orb orb-a"></div>
      </div>
      <div class="container container-shell">
        <div class="tag tag-pill">ABOUT LINSCIO</div>
        <h1>关于我们</h1>
        <p class="slogan">Think Together. Built for Academia.</p>
        <p class="sub">与你同思，为学而生 · 聆思恪 — 聆你所需，思你所问，恪守专业边界</p>
      </div>
    </section>

    <section class="section">
      <div class="container container-shell blocks">
        <article class="block card-base reveal">
          <h2>品牌定位</h2>
          <p><strong>LinScio AI · 聆思恪</strong> — Your AI Companion for Academic Knowledge Work，学术知识工作者的 AI 思维伙伴。</p>
          <p>中文名「聆思恪」作为品牌内核注脚，在品牌故事与本土化场景中诠释：<em>聆你所需，思你所问，恪守专业边界</em>。</p>
        </article>

        <article class="block card-base reveal">
          <h2>价值主张</h2>
          <p>LinScio AI 让学术知识工作者从繁琐的信息处理中解放出来，专注于真正需要人类判断力的思考与决策。</p>
          <p><strong>三大核心价值</strong>：<strong>专业</strong> — 真正懂学术，不是通用 AI 套壳；<strong>全场景</strong> — 科研·写作·管理·学习；<strong>本地化</strong> — 私有部署，数据安全合规。</p>
        </article>

        <article class="block card-base reveal">
          <h2>产品定位</h2>
          <p>学术领域 AI 智能体应用集群：涵盖文献管理、论文写作、科普创作、数据分析、质控工具等六大模块，支持 33 个专业智能体与多阶段工作流引擎，数据部署在用户本地，满足医疗数据安全与合规要求。</p>
        </article>

        <article class="block card-base reveal">
          <h2>联系我们</h2>
          <p>如需授权码、商务合作或技术支持，请通过官网或管理员渠道联系。感谢您选择 LinScio AI · 聆思恪。</p>
          <router-link to="/auth" class="btn btn-base btn-primary-ui">去注册 / 登录</router-link>
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
.about-v7 { min-height: calc(100vh - 68px); background: var(--color-bg-base); color: var(--color-text-body); }
.container { max-width: var(--container-max); margin: 0 auto; padding: 0 var(--space-6); }

.hero { position: relative; padding: var(--space-14) 0 24px; overflow: hidden; border-bottom: 1px solid var(--color-border-soft); background: linear-gradient(160deg, #f0f7ff 0%, #e8f2ff 40%, #f5f9ff 70%, #ffffff 100%); }
.hero-bg { position: absolute; inset: 0; }
.grid { position: absolute; inset: 0; background-image: linear-gradient(#dbeafe 1px, transparent 1px), linear-gradient(90deg, #dbeafe 1px, transparent 1px); background-size: 54px 54px; opacity: .35; }
.orb { position: absolute; border-radius: 50%; filter: blur(90px); }
.orb-a { width: 380px; height: 380px; top: -120px; right: -120px; background: rgba(59,130,246,.2); }
.hero .container { position: relative; z-index: 2; }
.hero h1 { margin: 14px 0 8px; font-size: clamp(30px, 4vw, 44px); color: var(--color-text-strong); }
.slogan { font-size: 19px; color: #1d4ed8; margin-bottom: 8px; }
.sub { color: #64748b; max-width: 760px; line-height: 1.7; }

.section { padding: var(--space-7) 0 var(--space-12); background: var(--color-bg-soft); }
.blocks { display: grid; gap: 14px; }
.block { border-radius: var(--radius-xl); padding: 22px; transition: all .25s ease; box-shadow: none; }
.block:hover {
  border-color: var(--color-border-brand);
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-2px);
}
.block h2 { margin-bottom: 10px; font-size: 22px; color: #0f172a; }
.block p { color: #475569; line-height: 1.75; margin-bottom: 10px; }
.block p:last-child { margin-bottom: 0; }

.btn { text-decoration: none; }

.reveal { opacity: 0; transform: translateY(18px); transition: all .5s ease; }
.reveal.visible { opacity: 1; transform: translateY(0); }
</style>
