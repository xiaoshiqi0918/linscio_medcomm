<template>
  <div ref="rootEl" class="home-v7">
    <section class="hero">
      <div class="hero-deco hero-deco-1"></div>
      <div class="hero-deco hero-deco-2"></div>
      <div class="hero-deco hero-deco-3"></div>
      <div class="container container-shell">
        <div class="hero-inner">
          <div>
            <div class="hero-badge reveal">
              <span class="hero-badge-icon">✦</span>
              专为高校科研人员 · 临床医生设计
            </div>
            <h1 class="hero-title reveal reveal-d1">
              让每位科研人
              <span class="hero-title-cn">拥有专属 AI 助手</span>
            </h1>
            <p class="hero-desc reveal reveal-d2">
              LinScio AI 覆盖学术论文写作、文献智能分析、医学科普、数据统计全流程，真实引用，专业规范，科研效率显著提升。
            </p>
            <div class="hero-actions reveal reveal-d3">
              <router-link to="/auth" class="btn btn-base btn-primary-ui btn-lg">免费开始使用</router-link>
              <router-link to="/download" class="btn btn-base btn-outline-ui btn-lg">下载桌面客户端</router-link>
            </div>
          </div>
          <div class="hero-visual reveal reveal-d2">
            <div class="hero-card">
              <div class="hero-card-header">
                <div class="hero-card-title">Schola · 学术写作助手</div>
                <div class="hero-card-badge">进行中</div>
              </div>
              <div class="hero-card-body">
                <div class="hero-progress-block">
                  <div class="hero-progress-label">
                    <span>正在生成：研究方法部分</span>
                    <span>阶段 3 / 7</span>
                  </div>
                  <div class="hero-progress-track"><div class="hero-progress-fill"></div></div>
                </div>
                <div class="hero-chat-msg hero-chat-user">采用回顾性队列研究设计，请帮我完善方法部分</div>
                <div class="hero-chat-msg hero-chat-ai">
                  根据 STROBE 报告规范，建议方法部分结构如下：研究设计、研究对象、结局指标与统计方法。
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="selling">
      <div class="container container-shell">
        <div class="section-header reveal">
          <div class="section-eyebrow">为什么选择 LinScio AI</div>
          <h2 class="section-title">不只是工具，更是科研伙伴</h2>
          <p class="section-desc">深度理解学术科研场景，专为高校科研人员与临床医生打造。</p>
        </div>
        <div class="selling-grid">
          <article v-for="(item, idx) in sellingPoints" :key="item.title" class="selling-card card-base reveal" :class="delayClass(idx)">
            <div class="selling-icon-wrap">{{ item.icon }}</div>
            <h3 class="selling-title">{{ item.title }}</h3>
            <p class="selling-desc">{{ item.desc }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="features">
      <div class="container container-shell">
        <div class="section-header reveal">
          <div class="section-eyebrow">核心功能</div>
          <h2 class="section-title">每一个功能，深思熟虑</h2>
          <p class="section-desc">不堆砌功能，只做科研人员真正需要的能力。</p>
        </div>
        <div class="features-tabs reveal">
          <button
            v-for="(tab, idx) in featureTabs"
            :key="tab.key"
            class="feature-tab"
            :class="{ active: activeFeature === idx }"
            @click="activeFeature = idx"
          >
            {{ tab.label }}
          </button>
        </div>
        <div class="feature-panel reveal reveal-d1">
          <div>
            <div class="feature-panel-tag">{{ featureTabs[activeFeature].tag }}</div>
            <h3 class="feature-panel-title">{{ featureTabs[activeFeature].title }}</h3>
            <p class="feature-panel-desc">{{ featureTabs[activeFeature].desc }}</p>
            <ul class="feature-list">
              <li v-for="point in featureTabs[activeFeature].points" :key="point">
                <span class="feature-list-check">✓</span>
                <span>{{ point }}</span>
              </li>
            </ul>
          </div>
          <div class="feature-visual card-base">
            <div class="fv-header">
              <div class="fv-dot" style="background:#ff5f57"></div>
              <div class="fv-dot" style="background:#febc2e"></div>
              <div class="fv-dot" style="background:#28c840"></div>
              <div class="fv-title">{{ featureTabs[activeFeature].mockTitle }}</div>
            </div>
            <div class="fv-body">
              <div class="fv-msg fv-msg-user">{{ featureTabs[activeFeature].mockUser }}</div>
              <div class="fv-msg fv-msg-ai">{{ featureTabs[activeFeature].mockAI }}</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="modules">
      <div class="container container-shell">
        <div class="section-header reveal">
          <div class="section-eyebrow">功能模块</div>
          <h2 class="section-title">五大模块，覆盖科研全场景</h2>
        </div>
        <div class="modules-grid">
          <article v-for="(m, idx) in modules" :key="m.name" class="module-card card-base reveal" :class="delayClass(idx)">
            <div class="module-icon">{{ m.icon }}</div>
            <h3 class="module-name">{{ m.name }}</h3>
            <p class="module-desc">{{ m.desc }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="faq">
      <div class="container container-shell small">
        <div class="section-header reveal">
          <div class="section-eyebrow">常见问题</div>
          <h2 class="section-title">你可能想知道的</h2>
        </div>
        <div class="faq-list">
          <article v-for="(faq, i) in faqs" :key="faq.q" class="faq-item card-base reveal" :class="{ open: openFaq === i }">
            <button class="faq-q" @click="openFaq = openFaq === i ? -1 : i">
              <span>{{ faq.q }}</span>
              <span class="faq-toggle">+</span>
            </button>
            <div class="faq-a" :style="{ maxHeight: openFaq === i ? '220px' : '0px' }">
              <div class="faq-a-inner">{{ faq.a }}</div>
            </div>
          </article>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const rootEl = ref(null)
const observer = ref(null)
const activeFeature = ref(0)
const openFaq = ref(-1)

function delayClass(idx) {
  return `reveal-d${(idx % 3) + 1}`
}

const sellingPoints = [
  { icon: '📚', title: '真实引用，杜绝幻觉', desc: '参考文献从文献库真实检索提取，每条引用可溯源核实。' },
  { icon: '🎯', title: '学科专属，深度调优', desc: '面向临床医学、高校科研场景，输出更专业。' },
  { icon: '⚡', title: '全流程覆盖，高效提升', desc: '覆盖从选题到投稿全流程，显著减少重复劳动。' },
  { icon: '🔒', title: '数据安全，本地优先', desc: '支持本地存储与内网环境，敏感数据更可控。' },
  { icon: '🤖', title: '多模型协作，弹性切换', desc: '支持主流大模型和本地模型，按任务灵活路由。' },
  { icon: '🏥', title: '医学场景专注', desc: '围绕医学科研工作流设计，不是通用工具套壳。' },
]

const featureTabs = [
  {
    key: 'write',
    label: '智能写作',
    tag: 'AI 学术写作',
    title: '从大纲到全文，多阶段智能写作',
    desc: '模拟专业科研写作流程，逐阶段推进，每个阶段均可审查修改。',
    points: ['支持多研究设计模板', '自动遵循 CONSORT/PRISMA/STROBE', '中英文双语写作支持'],
    mockTitle: 'Schola · 学术写作',
    mockUser: '采用回顾性队列研究，请帮我完善方法部分',
    mockAI: '建议按研究设计、对象、结局指标、统计方法四段组织，并按 STROBE 核对完整性。',
  },
  {
    key: 'paper',
    label: '文献分析',
    tag: '文献智能分析',
    title: '上传文献，秒级深度解析',
    desc: '批量上传 PDF，自动提取关键信息并关联分析，辅助系统综述。',
    points: ['章节自动识别与要点提取', '偏倚风险评估辅助', '跨文献一致性/矛盾点识别'],
    mockTitle: 'Literature · 文献分析',
    mockUser: '评估这篇 RCT 的研究质量',
    mockAI: '随机化充分，盲法部分实施，随访完整。综合评估：中等偏上。',
  },
  {
    key: 'data',
    label: '数据处理',
    tag: '数据分析辅助',
    title: '读懂数据，规范表达结果',
    desc: '将统计输出自动转化为学术规范文字，并辅助选择统计方法。',
    points: ['智能推荐统计方法', 'P 值/OR/HR/95%CI 规范输出', '图表与文字一体化解读'],
    mockTitle: 'Analyzer · 数据分析',
    mockUser: 't=3.24, df=48, p=0.002，如何写结果？',
    mockAI: '两组差异具有统计学意义（t=3.24, df=48, P=0.002），均值差 5.6（95%CI: 2.1-9.1）。',
  },
  {
    key: 'model',
    label: '多模型',
    tag: '多模型协作',
    title: '最优模型，智能路由分配',
    desc: '按任务类型自动选择模型，平衡质量与成本，支持本地离线模型。',
    points: ['支持 GPT / DeepSeek / Qwen 等', '任务分级自动路由', '支持 Ollama 本地模型'],
    mockTitle: '模型配置中心',
    mockUser: '核心写作任务，优先质量',
    mockAI: '已路由至高质量模型；快速任务将自动切换到高性价比模型。',
  },
]

const modules = [
  { icon: '✍️', name: 'Schola 学术写作', desc: '覆盖选题、综述、正文与投稿准备。' },
  { icon: '🏥', name: 'MedComm 医学科普', desc: '专业内容转化为可传播、可理解表达。' },
  { icon: '📖', name: 'Literature 文献分析', desc: '文献批量解析、关联与检索。' },
  { icon: '📊', name: 'Analyzer 数据分析', desc: '统计结果解读与学术化表述。' },
  { icon: '📋', name: 'QCC 品管圈', desc: '医疗质量改进流程与报告辅助。' },
]

const faqs = [
  { q: 'LinScio AI 和通用 AI 有什么区别？', a: 'LinScio AI 面向科研场景深度优化，强调真实引用、规范写作和流程可追溯。' },
  { q: '我的研究数据安全吗？', a: '支持本地优先与内网部署，敏感数据可控，不默认用于模型训练。' },
  { q: '支持高校内网环境吗？', a: '支持。可结合本地模型实现离线或半离线运行。' },
  { q: '支持哪些模型？', a: '支持主流云端模型与本地模型，可按任务质量/成本灵活切换。' },
]

onMounted(() => {
  observer.value = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible')
        observer.value?.unobserve(entry.target)
      }
    })
  }, { threshold: 0.12 })

  rootEl.value?.querySelectorAll('.reveal').forEach((el) => observer.value?.observe(el))
})

onBeforeUnmount(() => {
  observer.value?.disconnect()
})
</script>

<style scoped>
.home-v7 { color: var(--color-text-body); background: var(--color-bg-base); overflow-x: hidden; }
.container { max-width: var(--container-max); margin: 0 auto; padding: 0 var(--space-6); }
.container.small { max-width: 760px; }

.hero {
  min-height: 88vh;
  display: flex;
  align-items: center;
  padding-top: 20px;
  background: linear-gradient(160deg, #f0f7ff 0%, #e8f2ff 40%, #f5f9ff 70%, #ffffff 100%);
  position: relative;
  overflow: hidden;
}
.hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: linear-gradient(#dbeafe 1px, transparent 1px), linear-gradient(90deg, #dbeafe 1px, transparent 1px);
  background-size: 48px 48px;
  opacity: .35;
}
.hero-deco { position: absolute; border-radius: 50%; pointer-events: none; }
.hero-deco-1 { width: 520px; height: 520px; right: -80px; top: 50%; transform: translateY(-50%); background: radial-gradient(circle, rgba(219,234,254,.7) 0%, transparent 70%); filter: blur(40px); }
.hero-deco-2 { width: 280px; height: 280px; right: 100px; top: 10%; background: radial-gradient(circle, rgba(191,219,254,.6) 0%, transparent 70%); filter: blur(30px); }
.hero-deco-3 { width: 180px; height: 180px; left: 0; bottom: 8%; background: radial-gradient(circle, rgba(204,235,255,.5) 0%, transparent 70%); filter: blur(30px); }
.hero-inner { display: grid; grid-template-columns: 1fr 1fr; gap: 60px; align-items: center; position: relative; z-index: 1; }

.hero-badge { display: inline-flex; align-items: center; gap: var(--space-2); padding: 6px 14px; background: var(--color-bg-base); border: 1px solid var(--color-border-brand); border-radius: var(--radius-pill); font-size: 12.5px; color: var(--color-brand-700); font-weight: 500; }
.hero-badge-icon { width: 20px; height: 20px; display: inline-flex; align-items: center; justify-content: center; border-radius: 6px; background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: #fff; font-size: 11px; }
.hero-title { margin-top: var(--space-4); font-size: clamp(36px, 4.5vw, 56px); line-height: 1.1; letter-spacing: -1.2px; color: var(--color-text-strong); }
.hero-title-cn { display: block; color: var(--color-brand-700); font-family: 'Noto Serif SC', serif; }
.hero-desc { margin-top: var(--space-5); font-size: var(--fs-xl); color: var(--color-text-muted); line-height: 1.75; }
.hero-actions { margin-top: var(--space-7); display: flex; gap: var(--space-3); flex-wrap: wrap; }

.btn { transition: all .2s ease; }
.btn-lg { padding: var(--space-3) var(--space-6); }

.hero-card { background: #fff; border-radius: 20px; box-shadow: 0 12px 40px rgba(0,0,0,.1), 0 4px 12px rgba(0,0,0,.05); overflow: hidden; }
.hero-card-header { background: linear-gradient(135deg, #1d4ed8, #1e3a8a); padding: 18px 20px; display: flex; justify-content: space-between; color: #fff; }
.hero-card-title { font-size: 14px; font-weight: 600; }
.hero-card-badge { font-size: 11px; padding: 3px 10px; border-radius: 999px; background: rgba(255,255,255,.2); }
.hero-card-body { padding: 20px; display: grid; gap: 10px; }
.hero-progress-block { background: #eff6ff; border: 1px solid #dbeafe; border-radius: 12px; padding: 12px 14px; }
.hero-progress-label { display: flex; justify-content: space-between; font-size: 12px; color: #1d4ed8; margin-bottom: 7px; font-weight: 600; }
.hero-progress-track { height: 4px; background: #bfdbfe; border-radius: 99px; overflow: hidden; }
.hero-progress-fill { height: 100%; width: 60%; border-radius: 99px; background: linear-gradient(90deg, #3b82f6, #14b8a6); animation: progressSlide 2.5s ease-in-out infinite; }
.hero-chat-msg { border-radius: 12px; padding: 11px 14px; font-size: 13px; line-height: 1.6; }
.hero-chat-user { background: #2563eb; color: #fff; max-width: 86%; margin-left: auto; }
.hero-chat-ai { background: #f8fafc; border: 1px solid #e2e8f0; color: #334155; }

.selling, .features, .modules, .faq { padding: var(--space-22) 0; }
.features, .faq { background: #f7f9fc; }

.section-header { margin-bottom: 42px; text-align: center; }
.section-eyebrow { display: inline-flex; align-items: center; gap: 7px; font-size: var(--fs-xs); color: var(--color-brand-600); text-transform: uppercase; letter-spacing: .1em; font-weight: 600; }
.section-eyebrow::before { content: ''; width: 14px; height: 2px; background: var(--color-brand-600); border-radius: 2px; }
.section-title { margin-top: 14px; font-size: clamp(28px, 3.5vw, 42px); color: var(--color-text-strong); letter-spacing: -.6px; }
.section-desc { margin: 10px auto 0; max-width: 620px; color: var(--color-text-muted); font-size: var(--fs-lg); }

.selling-grid, .modules-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; }
.selling-card, .module-card { border-radius: var(--radius-2xl); padding: var(--space-6); transition: all .25s; box-shadow: none; }
.selling-card:hover, .module-card:hover { border-color: var(--color-border-brand); box-shadow: var(--shadow-card-hover); transform: translateY(-2px); }
.selling-icon-wrap, .module-icon { font-size: 24px; margin-bottom: 12px; }
.selling-title, .module-name { font-size: 17px; color: #0f172a; margin-bottom: 8px; }
.selling-desc, .module-desc { font-size: 14px; color: #64748b; line-height: 1.75; }

.features-tabs { display: flex; gap: 8px; justify-content: center; margin-bottom: 26px; border-bottom: 1.5px solid #e2e8f0; padding-bottom: 2px; }
.feature-tab { border: 0; background: transparent; color: #64748b; font-size: 14px; font-weight: 600; padding: 10px 16px; border-bottom: 2px solid transparent; cursor: pointer; }
.feature-tab.active { color: #1d4ed8; border-bottom-color: #2563eb; }
.feature-panel { display: grid; grid-template-columns: 1fr 1fr; gap: 42px; align-items: center; }
.feature-panel-tag { font-size: 12px; color: #0d9488; letter-spacing: .08em; text-transform: uppercase; font-weight: 600; }
.feature-panel-title { margin-top: 10px; font-size: 30px; line-height: 1.25; color: #0f172a; }
.feature-panel-desc { margin-top: 10px; color: #64748b; font-size: 15px; line-height: 1.8; }
.feature-list { list-style: none; margin-top: 16px; display: grid; gap: 10px; }
.feature-list li { display: flex; gap: 10px; color: #334155; font-size: 14px; }
.feature-list-check { width: 18px; height: 18px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; background: #dbeafe; color: #2563eb; font-size: 11px; margin-top: 2px; }
.feature-visual { border-radius: 20px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,.08); }
.fv-header { background: linear-gradient(135deg, #1e40af, #1e3a8a); padding: 14px 16px; display: flex; align-items: center; gap: 7px; }
.fv-dot { width: 9px; height: 9px; border-radius: 50%; }
.fv-title { margin-left: 6px; color: rgba(255,255,255,.75); font-size: 12px; }
.fv-body { padding: 16px; display: grid; gap: 10px; min-height: 230px; }
.fv-msg { border-radius: 10px; padding: 10px 13px; font-size: 13px; line-height: 1.6; }
.fv-msg-user { margin-left: auto; max-width: 86%; background: #2563eb; color: #fff; }
.fv-msg-ai { background: #f8fafc; border: 1px solid #e2e8f0; color: #334155; }

.faq-list { display: grid; gap: 10px; }
.faq-item { border-radius: 12px; overflow: hidden; box-shadow: none; }
.faq-item.open { border-color: #bfdbfe; box-shadow: 0 1px 4px rgba(59,130,246,.14); }
.faq-q { width: 100%; padding: 16px 18px; border: 0; background: transparent; display: flex; justify-content: space-between; align-items: center; text-align: left; color: #0f172a; font-size: 15px; font-weight: 600; cursor: pointer; }
.faq-toggle { width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; background: #e2e8f0; color: #64748b; transition: all .2s; }
.faq-item.open .faq-toggle { background: #2563eb; color: #fff; transform: rotate(45deg); }
.faq-a { overflow: hidden; transition: max-height .3s ease; }
.faq-a-inner { border-top: 1px solid #e2e8f0; padding: 12px 18px 16px; color: #475569; font-size: 14px; line-height: 1.75; }

.reveal { opacity: 0; transform: translateY(24px); transition: opacity .6s ease, transform .6s ease; }
.reveal.visible { opacity: 1; transform: translateY(0); }
.reveal-d1 { transition-delay: .1s; }
.reveal-d2 { transition-delay: .2s; }
.reveal-d3 { transition-delay: .3s; }

@keyframes progressSlide { 0% { width: 30%; } 50% { width: 75%; } 100% { width: 30%; } }
@media (max-width: 960px) {
  .hero-inner, .feature-panel { grid-template-columns: 1fr; }
  .selling-grid, .modules-grid { grid-template-columns: 1fr; }
}
</style>
