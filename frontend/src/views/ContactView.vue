<template>
  <div class="contact-page">
    <div class="contact-card">
      <h2 class="contact-title">联系我们</h2>
      <p class="contact-subtitle">如有任何问题、建议或合作意向，欢迎通过以下方式联系我们</p>

      <div class="contact-sections">
        <div class="contact-section">
          <div class="section-icon">✉️</div>
          <h3>电子邮箱</h3>
          <a class="email-link" href="mailto:linscio@163.com">linscio@163.com</a>
          <p class="section-hint">我们将在 5 个工作日内回复您的来信</p>
        </div>

        <div class="contact-divider" />

        <div class="contact-section">
          <p class="section-hint">扫描下方二维码添加客服</p>
          <div class="qr-wrapper">
            <img src="/wechat-service-qr.png" alt="客服二维码" class="qr-img" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.contact-page {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 48px 24px;
  min-height: 100%;
  background: #f5f7fa;
}

.contact-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  padding: 48px 56px;
  max-width: 520px;
  width: 100%;
  text-align: center;
}

.contact-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 8px;
}

.contact-subtitle {
  font-size: 0.9rem;
  color: #6b7280;
  margin: 0 0 36px;
}

.contact-sections {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.contact-section {
  padding: 24px 0;
}

.contact-section:first-child {
  padding-top: 0;
}

.contact-section:last-child {
  padding-bottom: 0;
}

.section-icon {
  font-size: 2rem;
  margin-bottom: 8px;
}

.contact-section h3 {
  font-size: 1.05rem;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 10px;
}

.email-link {
  display: inline-block;
  font-size: 1.1rem;
  font-weight: 500;
  color: #3b82f6;
  text-decoration: none;
  padding: 6px 20px;
  border-radius: 6px;
  background: rgba(59, 130, 246, 0.08);
  transition: background 0.2s;
}

.email-link:hover {
  background: rgba(59, 130, 246, 0.16);
}

.section-hint {
  font-size: 0.82rem;
  color: #9ca3af;
  margin: 8px 0 0;
}

.contact-divider {
  height: 1px;
  background: #f0f0f0;
  margin: 0;
}

.qr-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}

.qr-img {
  width: 220px;
  height: 220px;
  object-fit: contain;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
}
</style>
