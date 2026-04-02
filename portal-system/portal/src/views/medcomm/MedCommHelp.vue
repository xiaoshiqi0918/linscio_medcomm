<template>
  <div class="page container-shell">
    <h1>MedComm 帮助中心</h1>
    <div class="help-nav">
      <a href="#activate" class="anchor">激活教程</a>
      <a href="#device" class="anchor">换机指南</a>
      <a href="#migration" class="anchor">账号迁移申请</a>
    </div>

    <section id="activate" class="section">
      <h2>激活教程</h2>
      <ol class="steps">
        <li>在门户注册/登录后，进入「激活授权码」页面</li>
        <li>输入授权码（格式：LINSCIO-XXXX-XXXX-XXXX-XXXX），点击「验证授权码」</li>
        <li>确认预览信息无误后，填写设备信息并点击「确认激活」</li>
        <li>首次激活：点击「点击唤起软件」完成设备绑定；续费则无需额外操作</li>
      </ol>
      <router-link to="/medcomm/activate" class="link">前往激活 →</router-link>
    </section>

    <section id="device" class="section">
      <h2>换机指南</h2>
      <p>每个授权周期有 2 次自助换机机会。</p>
      <ol class="steps">
        <li>在新设备打开 MedComm 软件</li>
        <li>软件会要求输入账号密码，验证后显示 6 位换机码</li>
        <li>在已登录门户的浏览器中，进入「换机」页面输入该码完成换绑</li>
      </ol>
      <router-link to="/medcomm/device" class="link">前往换机 →</router-link>
      <router-link to="/medcomm/device/request" class="link">申请换机码 →</router-link>
    </section>

    <section id="migration" class="section">
      <h2>账号迁移申请</h2>
      <p>若原邮箱/手机号无法使用，可提交迁移申请，由客服在 1–3 个工作日内处理。</p>
      <router-link to="/medcomm/migration" class="link">提交迁移申请 →</router-link>
    </section>

    <router-link to="/medcomm/activate" class="back">← 返回</router-link>
  </div>
</template>

<style scoped>
.page { max-width: 640px; margin: 0 auto; padding: 100px 16px 48px; }
h1 { font-size: 1.75rem; margin-bottom: 24px; }
.help-nav { display: flex; gap: 16px; margin-bottom: 32px; flex-wrap: wrap; }
.anchor { color: #2563eb; text-decoration: none; }
.anchor:hover { text-decoration: underline; }
.section { margin-bottom: 28px; padding-bottom: 24px; border-bottom: 1px solid #e2e8f0; }
.section:last-of-type { border-bottom: none; }
.section h2 { font-size: 1.1rem; margin-bottom: 12px; }
.steps { margin: 12px 0; padding-left: 20px; line-height: 1.9; color: #334155; }
.link { display: inline-block; margin-top: 8px; margin-right: 16px; color: #2563eb; font-size: 14px; }
.back { display: inline-block; margin-top: 24px; color: #2563eb; }
</style>
