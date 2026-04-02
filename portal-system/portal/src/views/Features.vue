<template>
  <div class="features-v7">
    <section class="hero">
      <div class="hero-bg">
        <div class="grid"></div>
        <div class="orb orb-a"></div>
        <div class="orb orb-b"></div>
      </div>
      <div class="container container-shell">
        <div class="tag">FEATURES</div>
        <h1>六大智能模块，覆盖医学科研全场景</h1>
        <p>从文献管理、论文写作到科普创作、数据分析与质控，一站式 AI 科研助手。</p>
      </div>
    </section>

    <section class="section">
      <div class="container container-shell module-list">
        <article v-for="(mod, i) in modules" :key="mod.key" class="module-card card-base reveal" :style="{ transitionDelay: `${(i % 3) * 90}ms` }">
          <div class="head">
            <span class="num">{{ String(i + 1).padStart(2, '0') }}</span>
            <div>
              <h2>{{ mod.en }}</h2>
              <p class="cn">{{ mod.cn }}</p>
            </div>
          </div>
          <p class="desc">{{ mod.desc }}</p>
          <ul v-if="mod.features?.length" class="points">
            <li v-for="f in mod.features" :key="f">{{ f }}</li>
          </ul>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const modules = [
  {
    key: 'schola',
    en: 'LinScio Schola',
    cn: '学术论文智能辅助系统',
    desc: '覆盖选题评估、开题报告、大纲设计、章节写作、学术规范检查、投稿辅助与基金/伦理申请全流程，与文献模块协同完成引用与综述。',
    features: ['选题评估与可行性分析', '开题报告与立项材料生成', '大纲设计与字数分配', '学术规范与格式检查', '期刊推荐与 Cover Letter', '基金申请与伦理申请材料'],
  },
  {
    key: 'medcomm',
    en: 'MedComm Creator',
    cn: '医学科普内容创作',
    desc: '面向多平台（微信、知乎、小红书等）的科普内容生产，从选题、调研到素材整合与事实核查，输出合规、易懂的医学科普文案。',
    features: ['选题分析与角度建议', '调研规划与知识清单', '文献要点提取与术语通俗化', '医学信息事实核查', '多平台格式与风格适配'],
  },
  {
    key: 'qcc',
    en: 'QCC Assistant',
    cn: '质量控制智能助手',
    desc: '基于鱼骨图、5Why、柏拉图等经典质控方法，辅助根因分析与改进方案设计，支持 PDCA 循环与项目数据管理。',
    features: ['鱼骨图（6M1E）原因分析', '5Why 根因追溯', '柏拉图主因识别', '改进方案与对策矩阵', 'PDCA 循环管理'],
  },
  {
    key: 'image',
    en: 'AI Image Studio',
    cn: '一站式 AI 图像创作工作台',
    desc: '集成图像生成与编辑能力，为科研插图、科普配图等场景提供统一工作流，可与 ComfyUI 等外部服务对接。',
    features: ['科研插图与示意图', '多尺寸与多平台配图', '与 ComfyUI 等外部服务对接'],
  },
  {
    key: 'literature',
    en: 'LinScio Literature',
    cn: '文献管理与检索',
    desc: 'PDF 上传与解析、元数据/全文提取、多格式引用生成、文献综述（叙述性/系统/范围综述），以及基于 pgvector 的语义检索与相似推荐。',
    features: ['PDF 解析与元数据提取', '多格式引用（APA/MLA/GB 等）', '文献综述与趋势分析', '向量检索与相似文献推荐'],
  },
  {
    key: 'analyzer',
    en: 'Data Analyzer',
    cn: '数据分析与统计',
    desc: '支持 Excel/CSV/SPSS/SAS 等数据导入，完成分析规划、数据清洗、统计方法推荐、代码生成（Python/R）与结果解读。',
    features: ['分析流程规划与步骤拆解', '数据质量评估与清洗方案', '统计方法推荐与适用性分析', '可视化与结果解读'],
  },
]

const io = ref(null)

onMounted(() => {
  io.value = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible')
        io.value?.unobserve(entry.target)
      }
    })
  }, { threshold: 0.1 })
  document.querySelectorAll('.reveal').forEach((el) => io.value?.observe(el))
})

onBeforeUnmount(() => {
  io.value?.disconnect()
})
</script>

<style scoped>
.features-v7 { min-height: calc(100vh - 68px); background: var(--color-bg-base); color: var(--color-text-body); }
.container { max-width: var(--container-max); margin: 0 auto; padding: 0 var(--space-6); }
.hero { position: relative; padding: var(--space-14) 0 26px; overflow: hidden; border-bottom: 1px solid var(--color-border-soft); background: linear-gradient(160deg, #f0f7ff 0%, #e8f2ff 40%, #f5f9ff 70%, #ffffff 100%); }
.hero-bg { position: absolute; inset: 0; }
.grid { position: absolute; inset: 0; background-image: linear-gradient(#dbeafe 1px, transparent 1px), linear-gradient(90deg, #dbeafe 1px, transparent 1px); background-size: 54px 54px; opacity: .35; }
.orb { position: absolute; border-radius: 50%; filter: blur(90px); }
.orb-a { width: 380px; height: 380px; top: -120px; right: -120px; background: rgba(59,130,246,.2); }
.orb-b { width: 320px; height: 320px; bottom: -130px; left: -90px; background: rgba(45,212,191,.16); }
.hero .container { position: relative; z-index: 2; }
.tag { display: inline-block; padding: 4px 11px; border: 1px solid var(--color-border-brand); border-radius: var(--radius-pill); background: var(--color-bg-brand-soft); color: var(--color-brand-700); font-size: var(--fs-xs); }
.hero h1 { margin: 14px 0 10px; font-size: clamp(30px, 4vw, 46px); color: var(--color-text-strong); }
.hero p { color: var(--color-text-muted); max-width: 780px; line-height: 1.7; }

.section { padding: 28px 0 48px; background: #f8fafc; }
.module-list { display: grid; gap: 14px; }
.module-card { border-radius: var(--radius-xl); padding: 22px; transition: all .25s ease; box-shadow: none; }
.module-card:hover {
  border-color: var(--color-border-brand);
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-2px);
}
.head { display: flex; gap: 14px; align-items: center; margin-bottom: 12px; }
.num {
  width: 42px; height: 42px; border-radius: 10px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; font-weight: 700;
}
.head h2 { font-size: 22px; margin-bottom: 2px; color: #0f172a; }
.cn { color: #64748b; font-size: 14px; }
.desc { color: #475569; line-height: 1.75; margin-bottom: 10px; }
.points { margin: 0; padding-left: 18px; color: #334155; display: grid; gap: 6px; }

.reveal { opacity: 0; transform: translateY(18px); transition: all .5s ease; }
.reveal.visible { opacity: 1; transform: translateY(0); }
</style>
