<template>
  <div class="help-page page-container">
    <h2>帮助中心</h2>

    <!-- 目录导航 -->
    <div class="help-toc">
      <span class="toc-label">快速跳转：</span>
      <a href="#features" class="toc-link">功能介绍</a>
      <a href="#guide" class="toc-link">使用指导</a>
      <a v-if="!isElectron" href="#credits" class="toc-link">积分体系</a>
      <a v-if="!isElectron" href="#ai-pricing" class="toc-link">AI 计费明细</a>
      <a v-if="!isElectron" href="#model-strategy" class="toc-link">模型策略</a>
      <a v-if="isElectron" href="#llm-config" class="toc-link">模型配置</a>
      <a href="#llm-eval" class="toc-link">模型效果</a>
      <a href="#faq" class="toc-link">常见问题</a>
    </div>

    <!-- ════════════════ 功能介绍 ════════════════ -->
    <el-card id="features" class="help-card">
      <template #header>功能介绍</template>
      <div class="help-section">
        <h4>科普写作</h4>
        <p>支持 <strong>17 种科普内容形式</strong>（图文、短视频脚本、漫画分镜、情景剧本、科普故事等）× <strong>7 种发布平台</strong>（微信公众号、抖音、小红书、微博等），AI 根据选定形式和平台自动调整写作风格、篇幅和排版建议。</p>
        <ul>
          <li><strong>文献支撑</strong> — 导入 PubMed / 知网文献，AI 自动分析并在生成中引用，确保内容有据可查</li>
          <li><strong>分章节生成</strong> — 每种形式自动拆分为合理章节，支持单章生成或一键全文生成</li>
          <li><strong>声明核实</strong> — 生成后自动检查医学声明的准确性，标注存疑内容</li>
          <li><strong>阅读难度检测</strong> — 评估内容是否符合目标受众的阅读水平</li>
          <li><strong>多格式导出</strong> — 支持 HTML / DOCX / Markdown / PDF / TXT 导出</li>
        </ul>

        <h4>文献支撑库</h4>
        <p>在线检索 PubMed 文献，一键导入；支持 PDF 上传和全文解析。AI 分析摘要或全文后提取关键信息，在写作时自动引用。</p>

        <h4 v-if="isElectron">医学绘图</h4>
        <p v-if="isElectron">文生图 / 图生图，结合 ComfyUI 工作流，生成医学插图、科普配图。支持多种风格（写实、卡通、扁平等）和科室专业模板。</p>

        <h4>模板与知识库</h4>
        <p>内置模板库和知识库，可自定义写作模板结构。知识库为 AI 提供领域背景知识，提升生成质量。</p>

        <h4 v-if="isElectron">学科包</h4>
        <p v-if="isElectron">可下载安装学科专业包（如心血管、肿瘤、儿科等），包含该学科的专业词典、科普示例库，由 LinScio 团队持续维护更新。</p>
      </div>
    </el-card>

    <!-- ════════════════ 使用指导 ════════════════ -->
    <el-card id="guide" class="help-card">
      <template #header>使用指导</template>
      <div class="help-section">
        <h4>快速开始：创建一篇科普文章</h4>
        <ol class="guide-steps">
          <li><strong>准备文献</strong> — 在「文献支撑库」中搜索或上传 2-5 篇相关文献，AI 会自动分析</li>
          <li><strong>新建文章</strong> — 点击「科普写作」→「新建文章」，填写主题、选择内容形式和发布平台</li>
          <li><strong>绑定文献</strong> — 在文章配置中勾选已导入的文献作为参考来源</li>
          <li><strong>生成内容</strong> — 点击「一键生成全文」或逐章节生成，AI 会基于文献撰写内容</li>
          <li><strong>编辑润色</strong> — 在编辑器中修改内容，可使用「润色优化」功能改善表达</li>
          <li><strong>导出发布</strong> — 选择目标格式导出，复制到对应平台发布</li>
        </ol>

        <h4>文献分析说明</h4>
        <p>文献分析支持两种模式：</p>
        <ul>
          <li><strong>摘要分析</strong> — 仅分析论文标题和摘要，速度快、消耗少，适合快速筛选</li>
          <li><strong>全文分析</strong> — 解析 PDF 全文内容，提取方法、结果、结论等详细信息，适合深度引用</li>
        </ul>
        <p>建议每篇文章绑定 <strong>3 篇以上</strong>文献以获得最佳生成效果。绑定文献不足时系统会提示警告。</p>
      </div>
    </el-card>

    <!-- ════════════════ SaaS：积分体系 ════════════════ -->
    <el-card v-if="!isElectron" id="credits" class="help-card">
      <template #header>积分体系</template>
      <div class="help-section">
        <h4>积分类型</h4>
        <el-table :data="creditTypes" stripe size="small" style="width: 100%;">
          <el-table-column prop="type" label="类型" width="120" />
          <el-table-column prop="source" label="获取方式" min-width="200" />
          <el-table-column prop="usage" label="可用范围" min-width="200" />
          <el-table-column prop="model" label="可用模型" width="140" />
        </el-table>

        <h4>积分获取方式</h4>
        <div class="rule-block">
          <div class="rule-item"><span class="rule-tag primary">兑换码充值</span> 使用管理员分发的兑换码充值，1 元 = 1 积分，50 元及以上档位享有赠送积分</div>
          <div class="rule-item"><span class="rule-tag primary">在线支付</span> 支持支付宝 / 微信支付，1 元 = 1 积分，充值越多赠送比例越高（最高 12%）</div>
          <div class="rule-item"><span class="rule-tag success">注册</span> 新用户注册即赠 3 积分，有效期 30 天</div>
          <div class="rule-item"><span class="rule-tag success">推广注册</span> 好友通过您的推广链接注册，您获得 5 推广积分</div>
          <div class="rule-item"><span class="rule-tag success">推广返利</span> 好友每次充值（≥50元，含兑换码充值），您获得其充值积分 10% 的推广积分</div>
        </div>

        <h4>文章生成 — 分档计费</h4>
        <p class="help-note" style="margin-bottom: 8px;">SaaS 版本会根据您的账户类型自动选择最佳模型，不同档位的模型消耗积分不同：</p>
        <el-table :data="modelTierPricing" stripe size="small" style="width: 100%;">
          <el-table-column prop="words" label="字数范围" width="140" />
          <el-table-column prop="basic" label="基础档" width="100">
            <template #default="{ row }"><span style="color: #6b7280;">{{ row.basic }}</span></template>
          </el-table-column>
          <el-table-column prop="standard" label="标准档" width="100">
            <template #default="{ row }"><span style="color: #2563eb;">{{ row.standard }}</span></template>
          </el-table-column>
          <el-table-column prop="pro" label="专业档" width="100">
            <template #default="{ row }"><strong style="color: #9333ea;">{{ row.pro }}</strong></template>
          </el-table-column>
        </el-table>
        <el-table :data="modelTierExamples" stripe size="small" style="width: 100%; margin-top: 8px;">
          <el-table-column prop="tier" label="档位" width="100" />
          <el-table-column prop="models" label="包含模型" min-width="260" />
          <el-table-column prop="desc" label="特点" min-width="200" />
        </el-table>
        <div class="rule-block" style="margin-top: 12px;">
          <div class="rule-item"><span class="rule-tag">固定模型</span> SaaS 版各功能使用固定模型，无需手动选择；充值积分用户使用专业档模型（GPT-4o），赠送/推广积分用户使用基础档模型（DeepSeek）</div>
          <div class="rule-item"><span class="rule-tag">故障降级</span> 仅在当前模型不可用时自动切换至备选模型，降级后按实际使用模型的档位计费（费用更低）</div>
          <div class="rule-item"><span class="rule-tag primary">手动选择</span> 如需自选模型，请下载桌面客户端，配置您自己的 API Key</div>
        </div>

        <h4 id="ai-pricing">各 AI 功能详细计费说明</h4>
        <p class="help-note" style="margin-bottom: 12px;">每次 AI 操作自动开启一个计费会话，会话内所有模型调用统一结算。操作前预估费用并冻结积分，完成后按实际 token 用量结算（不超过预估额），失败或中断时全额退还。</p>

        <el-table :data="aiDetailRules" stripe size="small" style="width: 100%;" :span-method="aiDetailSpan">
          <el-table-column prop="operation" label="AI 功能" width="130" />
          <el-table-column prop="model" label="调用模型" width="150" />
          <el-table-column prop="inputRule" label="输入费用" min-width="200" />
          <el-table-column prop="outputRule" label="输出费用" min-width="200" />
          <el-table-column prop="example" label="典型费用" width="120">
            <template #default="{ row }"><strong style="color: #1e40af;">{{ row.example }}</strong></template>
          </el-table-column>
        </el-table>

        <div class="rule-block" style="margin-top: 12px;">
          <div class="rule-item"><span class="rule-tag">计费会话</span> 每次用户操作（如生成一个章节、分析一篇文献）对应一个计费会话，会话内所有 LLM 调用统一结算，只产生一次扣费记录</div>
          <div class="rule-item"><span class="rule-tag">结算逻辑</span> 操作前按输入量预估总费用并冻结积分 → 完成后按实际 token 用量结算 → 实际费用 ≤ 预估费用（多退不补扣）</div>
          <div class="rule-item"><span class="rule-tag success">中断保护</span> 生成中断或失败时，全额退还冻结积分、不扣费（平台承担损失，保障用户权益）</div>
          <div class="rule-item"><span class="rule-tag primary">模型降级</span> 充值积分用户使用专业档模型（GPT-4o）；赠送/推广积分用户降级为基础档（DeepSeek），费用更低</div>
        </div>

        <h4>其他费用</h4>
        <el-table :data="otherCostRules" stripe size="small" style="width: 100%;">
          <el-table-column prop="operation" label="操作" width="140" />
          <el-table-column prop="condition" label="条件" min-width="200" />
          <el-table-column prop="cost" label="消耗积分" width="120" />
        </el-table>
        <p class="help-note">扣费优先级：赠送积分 → 推广积分 → 充值积分。</p>

        <h4>完整流程预估费用</h4>
        <p>以一篇 <strong>2000 字微信公众号图文</strong>为例，绑定 <strong>3 篇文献</strong>（摘要分析），完整流程费用预估：</p>
        <el-table :data="estimateExample" stripe size="small" style="width: 100%;">
          <el-table-column prop="step" label="步骤" width="60" />
          <el-table-column prop="operation" label="操作" width="160" />
          <el-table-column prop="model" label="调用模型" width="140" />
          <el-table-column prop="detail" label="说明" min-width="200" />
          <el-table-column prop="cost" label="积分" width="100">
            <template #default="{ row }"><strong v-if="row.cost && row.cost !== '免费'" style="color: #1e40af;">{{ row.cost }}</strong><span v-else>{{ row.cost }}</span></template>
          </el-table-column>
        </el-table>
        <div class="estimate-summary">
          <div class="estimate-row"><span>基础流程（检索词设计 + 文献分析 + 全文生成 + 带水印导出）</span><strong>≈ 8~11 积分（¥8~11）</strong></div>
          <div class="estimate-row"><span>完整流程（含翻译 + AI 写作 + 润色 + 配图提示词 + 无水印导出）</span><strong>≈ 14~19 积分（¥14~19）</strong></div>
          <div class="estimate-row highlight"><span>新用户赠送 3 积分，可体验一次短篇生成（≤1000 字，不含文献分析）</span></div>
        </div>
        <p class="help-note">以上为专业档模型（GPT-4o）的典型预估，使用基础档模型（DeepSeek）费用约为 40%~50%。实际费用因文献篇幅、生成长度、润色次数等略有浮动。</p>

        <h4 style="margin-top: 24px;">不同场景费用参考</h4>
        <el-table :data="scenarioEstimates" stripe size="small" style="width: 100%;">
          <el-table-column prop="scenario" label="场景" min-width="260" />
          <el-table-column prop="litCost" label="文献分析" width="100" />
          <el-table-column prop="genCost" label="生成" width="80" />
          <el-table-column prop="extraCost" label="润色+导出" width="100" />
          <el-table-column prop="total" label="合计预估" width="100">
            <template #default="{ row }"><strong style="color: #1e40af;">{{ row.total }}</strong></template>
          </el-table-column>
        </el-table>

        <h4>充值套餐（兑换码 / 在线支付通用）</h4>
        <el-table :data="rechargePlans" stripe size="small" style="width: 100%;">
          <el-table-column prop="amount" label="金额" width="80">
            <template #default="{ row }">¥{{ row.amount }}</template>
          </el-table-column>
          <el-table-column prop="credits" label="积分" width="80" />
          <el-table-column prop="bonus" label="赠送" width="80" />
          <el-table-column prop="total" label="合计" width="80">
            <template #default="{ row }">{{ row.credits + row.bonus }}</template>
          </el-table-column>
          <el-table-column prop="unitPrice" label="单价" width="120" />
          <el-table-column prop="codePrefix" label="兑换码前缀" width="120" />
        </el-table>
        <p class="help-note" style="margin-top: 8px;">兑换码由管理员生成并分发，每个兑换码仅限使用一次。在「设置 → 充值积分 → 兑换码充值」中输入兑换码即可完成充值。</p>

        <h4>推广积分使用</h4>
        <ul>
          <li>折现提取：1 推广积分 = 0.1 元（最低 100 积分起提）</li>
          <li>兑换客户端下载授权码：1000 推广积分 / 个</li>
          <li>积分兑换客户端授权码：600 积分（充值+赠送积分均可）</li>
          <li>推广积分也可用于抵扣生成消耗（使用基础模型）</li>
        </ul>
      </div>
    </el-card>

    <!-- ════════════════ SaaS：模型策略 ════════════════ -->
    <el-card v-if="!isElectron" id="model-strategy" class="help-card">
      <template #header>AI 模型使用策略</template>
      <div class="help-section">
        <p>系统会根据您的积分类型自动选择最合适的 AI 模型，无需手动切换。</p>

        <el-table :data="modelStrategy" stripe size="small" style="width: 100%;">
          <el-table-column prop="condition" label="积分状态" width="200" />
          <el-table-column prop="models" label="使用模型" min-width="240" />
          <el-table-column prop="quality" label="生成质量" width="120" />
        </el-table>

        <div class="strategy-tip">
          <el-alert type="info" :closable="false" show-icon>
            <template #title>
              <strong>如何获得最佳写作效果？</strong> 确保账户有充值积分余额，系统将自动使用 ChatGPT、Gemini 等高质量模型。
              当充值积分耗尽、仅剩赠送或推广积分时，系统自动切换为基础模型（DeepSeek），仍能满足日常写作需求。
            </template>
          </el-alert>
        </div>

        <h4>模型降级与恢复</h4>
        <ul>
          <li>充值积分 > 0 时，始终使用高质量模型</li>
          <li>充值积分耗尽后，自动降级为基础模型</li>
          <li>任意金额充值后，立即恢复高质量模型</li>
          <li>系统支持多模型自动降级容灾：主模型不可用时自动切换备选模型，确保服务不中断</li>
        </ul>
      </div>
    </el-card>

    <!-- ════════════════ 桌面端：模型配置 ════════════════ -->
    <el-card v-if="isElectron" id="llm-config" class="help-card">
      <template #header>模型配置指南</template>
      <div class="help-section">
        <p>桌面客户端使用您自己的 API Key 调用大语言模型，数据不经过 LinScio 服务器，隐私安全。</p>

        <h4>支持的模型服务商</h4>
        <el-table :data="desktopProviders" stripe size="small" style="width: 100%;">
          <el-table-column prop="provider" label="服务商" width="140" />
          <el-table-column prop="models" label="可用模型" min-width="250" />
          <el-table-column prop="tip" label="说明" min-width="200" />
        </el-table>

        <h4>配置方法</h4>
        <ol class="guide-steps">
          <li>前往「设置」页面，找到「API Key」部分</li>
          <li>在对应服务商栏位粘贴您的 API Key</li>
          <li>点击保存，系统会自动检测 Key 的有效性</li>
          <li>在「模型配置」中选择默认模型</li>
        </ol>
        <p class="help-note">API Key 存储在系统 Keychain 中（macOS Keychain / Windows Credential Manager），不以明文保存。</p>

        <h4>模型选择建议</h4>
        <ul>
          <li><strong>追求质量</strong> — 推荐 ChatGPT (GPT-4o) 或 Gemini Pro，生成内容更精准流畅</li>
          <li><strong>控制成本</strong> — 推荐 DeepSeek Chat，性价比极高，日常写作完全够用</li>
          <li><strong>免费体验</strong> — 智谱 GLM-4-Flash 免费额度较高，适合初次体验</li>
        </ul>
      </div>
    </el-card>

    <!-- ════════════════ 模型效果评测 ════════════════ -->
    <el-card id="llm-eval" class="help-card">
      <template #header>AI 模型效果评测</template>
      <div class="help-section">
        <p>以下评测基于医学科普写作场景实测（2000 字图文、3 篇参考文献），评分为相对比较，仅供参考：</p>

        <el-table :data="modelEval" stripe size="small" style="width: 100%;">
          <el-table-column prop="model" label="模型" width="160" />
          <el-table-column prop="accuracy" label="专业准确性" width="110">
            <template #default="{ row }"><span :class="'eval-' + row.accuracyLevel">{{ row.accuracy }}</span></template>
          </el-table-column>
          <el-table-column prop="fluency" label="语言流畅度" width="110">
            <template #default="{ row }"><span :class="'eval-' + row.fluencyLevel">{{ row.fluency }}</span></template>
          </el-table-column>
          <el-table-column prop="citation" label="文献引用" width="110">
            <template #default="{ row }"><span :class="'eval-' + row.citationLevel">{{ row.citation }}</span></template>
          </el-table-column>
          <el-table-column prop="speed" label="生成速度" width="100">
            <template #default="{ row }"><span :class="'eval-' + row.speedLevel">{{ row.speed }}</span></template>
          </el-table-column>
          <el-table-column prop="summary" label="总结" min-width="200" />
        </el-table>

        <p class="help-note">评测结果受提示词、文献质量、主题复杂度等因素影响，不同场景下可能有差异。所有模型均经过医学科普场景优化提示词调教。</p>
      </div>
    </el-card>

    <!-- ════════════════ 常见问题 ════════════════ -->
    <el-card id="faq" class="help-card">
      <template #header>常见问题</template>
      <div class="help-section">
        <el-collapse>
          <el-collapse-item title="生成的内容医学准确性如何保证？" name="1">
            <p>系统采用多重机制保障准确性：①文献支撑 — AI 基于真实文献撰写，自动引用出处；②声明核实 — 生成后自动检查医学声明；③知识库 — 内置医学知识库提供领域约束。但 AI 生成内容仍需专业人员审核后再发布。</p>
          </el-collapse-item>
          <el-collapse-item title="生成中途中断了，积分怎么算？" name="2">
            <p>中断或失败时，系统会全额退还已冻结的积分，不扣取任何费用。只有当操作成功完成后，才会按实际用量结算。平台优先保障用户权益，中断产生的 LLM 成本由平台承担。</p>
          </el-collapse-item>
          <el-collapse-item v-if="!isElectron" title="赠送积分和充值积分有什么区别？" name="3">
            <p>主要区别在于可使用的 AI 模型：充值积分可使用 ChatGPT、Gemini 等高质量模型；赠送积分和推广积分仅可使用 DeepSeek 基础模型。充值积分无有效期限制，赠送积分有 30 天有效期。</p>
          </el-collapse-item>
          <el-collapse-item title="如何让文章质量更高？" name="4">
            <p>①绑定 3 篇以上高质量文献；②选择合适的内容形式和平台；③使用润色优化功能改善表达；④利用个人语料库建立写作风格；⑤设置合适的目标字数和阅读难度。</p>
          </el-collapse-item>
          <el-collapse-item v-if="isElectron" title="API Key 安全吗？" name="5">
            <p>API Key 存储在操作系统的安全凭证管理器中（macOS Keychain / Windows Credential Manager），不以明文保存在磁盘上，且 API 调用直接从您的电脑发送到模型服务商，不经过 LinScio 服务器。</p>
          </el-collapse-item>
          <el-collapse-item v-if="!isElectron" title="SaaS 版和客户端有什么区别？" name="6">
            <p>SaaS 网页版无需安装，即开即用，支持科普写作核心功能。桌面客户端额外支持：医学绘图（文生图/图生图）、学科包、医学词典管理、科普示例库、本地数据存储、自选 AI 模型等高级功能。可在设置页面兑换客户端授权码后下载。</p>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
const isElectron = typeof window !== 'undefined' && !!(window as any).electronAPI?.isElectron

const creditTypes = [
  { type: '充值积分', source: '兑换码充值 / 在线充值（1元=1积分）', usage: '所有功能', model: '高质量模型' },
  { type: '赠送积分', source: '新用户注册赠送 3 积分', usage: '所有功能', model: '基础模型' },
  { type: '推广积分', source: '邀请好友注册/充值返利', usage: '生成消耗 / 折现 / 兑换授权码', model: '基础模型' },
]

const modelTierPricing = [
  { words: '≤1000 字', basic: '2', standard: '3', pro: '5' },
  { words: '≤2000 字', basic: '3', standard: '5', pro: '8' },
  { words: '≤3000 字', basic: '5', standard: '8', pro: '12' },
  { words: '≤5000 字', basic: '8', standard: '12', pro: '18' },
  { words: '超出每 1000 字', basic: '+1', standard: '+2', pro: '+3' },
]

const modelTierExamples = [
  { tier: '基础档', models: 'DeepSeek、通义千问、GLM-4-Flash', desc: '赠送/推广积分用户使用，性价比高' },
  { tier: '标准档', models: 'Kimi K2.5、Gemini Flash、Qwen-Max', desc: '部分辅助任务使用（文献分析等）' },
  { tier: '专业档', models: 'GPT-4o、Gemini Pro', desc: '充值用户的文章生成默认使用' },
]

const aiDetailRules = [
  // 文章生成
  { operation: '文章生成', model: 'GPT-4o（专业档）', inputRule: '按目标字数阶梯：≤1K→5 / ≤2K→8 / ≤3K→12 / ≤5K→18', outputRule: '按实际 token 用量结算，不超过预估', example: '≈ 3~18', _rowspan: 3 },
  { operation: '文章生成', model: 'DeepSeek（基础档）', inputRule: '按目标字数阶梯：≤1K→2 / ≤2K→3 / ≤3K→5 / ≤5K→8', outputRule: '按实际 token 用量结算，不超过预估', example: '≈ 2~8' },
  { operation: '文章生成', model: '文献 Embedding', inputRule: '绑定文献时额外 +0.1（向量检索附加费）', outputRule: '—', example: '+0.1' },
  // 文献分析
  { operation: '文献摘要分析', model: 'Kimi K2.5', inputRule: '按摘要总字符：≤3K→0.3 / ≤8K→0.3 / ≤15K→0.5 / ≤30K→0.5', outputRule: '每 1000 输出字符 × 0.8 积分', example: '≈ 1~4/篇', _rowspan: 2 },
  { operation: '文献全文分析', model: 'Gemini Pro', inputRule: '按全文总字符：≤3K→0.5 / ≤8K→1 / ≤15K→2 / ≤30K→3', outputRule: '每 1000 输出字符 × 1.2 积分', example: '≈ 2~8/篇' },
  // 润色
  { operation: '润色优化', model: 'GPT-4o', inputRule: '按输入字符：≤500→0.5 / ≤1K→1 / ≤2K→1.5 / 超出每 1K +0.8', outputRule: '每 1000 输出字符 × 0.6 积分', example: '≈ 1~3' },
  // 翻译
  { operation: 'AI 翻译', model: 'DeepSeek', inputRule: '按原文字符：≤500→0.05 / ≤2K→0.1 / ≤5K→0.2 / ≤15K→0.4', outputRule: '每 1000 译文字符 × 0.3 积分', example: '≈ 0.1~1' },
  // AI 辅助写作
  { operation: 'AI 辅助写作', model: 'GPT-4o', inputRule: '按选中字符：≤500→0.1 / ≤1.5K→0.2 / ≤3K→0.3', outputRule: '每 1000 输出字符 × 0.5 积分', example: '≈ 0.2~2' },
  // 文献筛选
  { operation: '文献 AI 筛选', model: 'DeepSeek', inputRule: '按文献篇数：≤10→0.5 / ≤20→1 / ≤30→1.5 / ≤50→2 / >50→3', outputRule: '—（筛选结果不产生长文本输出）', example: '≈ 0.5~3' },
  // 检索词智能设计
  { operation: '检索词智能设计', model: 'DeepSeek', inputRule: '固定费用', outputRule: '—', example: '0.1' },
  // 配图 AI 提示词
  { operation: '配图 AI 提示词', model: 'DeepSeek', inputRule: '固定费用（生成或优化每次）', outputRule: '—', example: '0.2' },
]

function aiDetailSpan({ row, columnIndex }: { row: any; column: any; rowIndex: number; columnIndex: number }) {
  if (columnIndex === 0 && row._rowspan) {
    return { rowspan: row._rowspan, colspan: 1 }
  }
  return { rowspan: 1, colspan: 1 }
}

const otherCostRules = [
  { operation: '无水印导出', condition: '每次', cost: '3' },
  { operation: '带水印导出', condition: '每次', cost: '免费' },
  { operation: '首篇文章', condition: '新用户首次生成', cost: '免费' },
]

const estimateExample = [
  { step: '1', operation: '检索词智能设计', model: 'DeepSeek', detail: '输入主题描述，AI 自动生成 PubMed 检索策略', cost: '0.1' },
  { step: '2', operation: '文献摘要分析 ×3', model: 'Kimi K2.5', detail: '3 篇 PubMed 摘要（输入 ~3K + 输出 ~9K 字符）', cost: '≈ 3' },
  { step: '3', operation: '一键生成全文', model: 'GPT-4o', detail: '2000 字图文（含引言/正文/结语 + 文献 Embedding）', cost: '≈ 5~8' },
  { step: '4', operation: '带水印导出', model: '—', detail: 'HTML / DOCX 格式导出', cost: '免费' },
  { step: '', operation: '', model: '', detail: '— 以下为可选操作 —', cost: '' },
  { step: '5', operation: 'AI 翻译文献 ×3', model: 'DeepSeek', detail: '翻译 3 篇摘要（输入 ~3K + 输出 ~2K 字符）', cost: '≈ 0.5~1' },
  { step: '6', operation: 'AI 辅助写作 ×2', model: 'GPT-4o', detail: '选中段落续写/改写（输入 ~0.5K + 输出 ~0.5K ×2）', cost: '≈ 0.6' },
  { step: '7', operation: '润色优化 ×1', model: 'GPT-4o', detail: '对正文章节做一次润色（输入 ~1K + 输出 ~0.8K）', cost: '≈ 1.5' },
  { step: '8', operation: '配图 AI 提示词 ×2', model: 'DeepSeek', detail: '为 2 张配图生成/优化提示词', cost: '0.4' },
  { step: '9', operation: '无水印导出', model: '—', detail: '去除水印的正式版导出', cost: '3' },
]

const scenarioEstimates = [
  { scenario: '短视频脚本（800字 + 2篇摘要分析）', litCost: '≈ 2', genCost: '≈ 3', extraCost: '0 ~ 6', total: '≈ 5 ~ 11' },
  { scenario: '微信图文（2000字 + 3篇摘要分析）', litCost: '≈ 3', genCost: '≈ 5~8', extraCost: '0 ~ 6', total: '≈ 8 ~ 17' },
  { scenario: '深度长文（4000字 + 5篇全文分析）', litCost: '≈ 10~20', genCost: '≈ 12', extraCost: '0 ~ 8', total: '≈ 22 ~ 40' },
  { scenario: '漫画分镜（1500字 + 3篇摘要分析）', litCost: '≈ 3', genCost: '≈ 5', extraCost: '0 ~ 6', total: '≈ 8 ~ 14' },
  { scenario: '情景剧本（3000字 + 5篇摘要分析）', litCost: '≈ 5', genCost: '≈ 8~12', extraCost: '0 ~ 6', total: '≈ 13 ~ 23' },
]

const rechargePlans = [
  { amount: 10, credits: 10, bonus: 0, unitPrice: '1.00 元/积分', codePrefix: 'LS0A-****' },
  { amount: 50, credits: 50, bonus: 3, unitPrice: '0.94 元/积分', codePrefix: 'LS3B-****' },
  { amount: 100, credits: 100, bonus: 8, unitPrice: '0.93 元/积分', codePrefix: 'LS5C-****' },
  { amount: 300, credits: 300, bonus: 30, unitPrice: '0.91 元/积分', codePrefix: 'LS7D-****' },
  { amount: 500, credits: 500, bonus: 60, unitPrice: '0.89 元/积分', codePrefix: 'LS9E-****' },
]

const modelStrategy = [
  { condition: '有充值积分余额', models: '标准档 / 专业档模型（GPT-4o、Gemini Pro、Kimi K2.5 等）', quality: '⭐⭐⭐⭐⭐' },
  { condition: '仅剩赠送或推广积分', models: '基础档模型（DeepSeek）', quality: '⭐⭐⭐' },
]

const desktopProviders = [
  { provider: 'OpenAI', models: 'GPT-4o / GPT-4o-mini', tip: '综合质量最佳，推荐首选' },
  { provider: 'DeepSeek', models: 'DeepSeek Chat / Reasoner', tip: '性价比极高，国内直连快' },
  { provider: 'Google', models: 'Gemini Pro / Flash', tip: '长文本理解出色' },
  { provider: '通义千问', models: 'Qwen-Max / Plus / Turbo', tip: '中文表达自然' },
  { provider: 'Moonshot', models: 'Kimi K2.5 / K2-Turbo', tip: '长上下文支持好' },
  { provider: '智谱', models: 'GLM-4.7 / GLM-4-Flash', tip: 'Flash 有免费额度' },
  { provider: '硅基流动', models: '多模型聚合', tip: '按量付费，模型选择丰富' },
]

const modelEval = [
  { model: 'ChatGPT (GPT-4o)', accuracy: '★★★★★', accuracyLevel: 'high', fluency: '★★★★★', fluencyLevel: 'high', citation: '★★★★☆', citationLevel: 'high', speed: '★★★☆☆', speedLevel: 'mid', summary: '综合最优，专业性与文笔俱佳' },
  { model: 'Gemini Pro', accuracy: '★★★★☆', accuracyLevel: 'high', fluency: '★★★★☆', fluencyLevel: 'high', citation: '★★★★★', citationLevel: 'high', speed: '★★★☆☆', speedLevel: 'mid', summary: '文献理解能力突出，长文表现稳定' },
  { model: 'DeepSeek Chat', accuracy: '★★★★☆', accuracyLevel: 'high', fluency: '★★★★☆', fluencyLevel: 'high', citation: '★★★☆☆', citationLevel: 'mid', speed: '★★★★★', speedLevel: 'high', summary: '性价比之王，速度快，日常够用' },
  { model: 'Kimi K2.5', accuracy: '★★★★☆', accuracyLevel: 'high', fluency: '★★★★☆', fluencyLevel: 'high', citation: '★★★★☆', citationLevel: 'high', speed: '★★★☆☆', speedLevel: 'mid', summary: '中文科普写作自然，长文稳定' },
  { model: '通义 Qwen-Max', accuracy: '★★★★☆', accuracyLevel: 'high', fluency: '★★★★★', fluencyLevel: 'high', citation: '★★★☆☆', citationLevel: 'mid', speed: '★★★★☆', speedLevel: 'high', summary: '中文表达最自然，科普亲和力强' },
  { model: '智谱 GLM-4-Flash', accuracy: '★★★☆☆', accuracyLevel: 'mid', fluency: '★★★☆☆', fluencyLevel: 'mid', citation: '★★☆☆☆', citationLevel: 'low', speed: '★★★★★', speedLevel: 'high', summary: '免费额度高，适合入门体验' },
]
</script>

<style scoped>
.help-page {
  max-width: 900px;
  margin: 0 auto;
}
.help-page h2 {
  margin-bottom: 16px;
}
.help-toc {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 20px;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}
.toc-label {
  font-size: 0.85rem;
  color: #6b7280;
  font-weight: 600;
}
.toc-link {
  font-size: 0.85rem;
  color: #2563eb;
  text-decoration: none;
  padding: 2px 10px;
  border-radius: 4px;
  transition: background 0.15s;
}
.toc-link:hover {
  background: #dbeafe;
}
.help-card {
  margin-bottom: 20px;
  scroll-margin-top: 80px;
}
.help-section h4 {
  font-size: 1rem;
  color: #1e293b;
  margin: 20px 0 8px 0;
  padding-bottom: 4px;
  border-bottom: 1px solid #f1f5f9;
}
.help-section h4:first-child {
  margin-top: 4px;
}
.help-section p {
  font-size: 0.9rem;
  color: #4b5563;
  line-height: 1.7;
  margin: 6px 0;
}
.help-section ul, .help-section ol {
  padding-left: 20px;
  margin: 8px 0;
}
.help-section li {
  font-size: 0.9rem;
  color: #4b5563;
  line-height: 1.8;
}
.guide-steps li {
  margin-bottom: 6px;
}
.help-note {
  font-size: 0.82rem !important;
  color: #9ca3af !important;
  margin-top: 10px !important;
  font-style: italic;
}
.rule-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 8px 0;
}
.rule-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.9rem;
  color: #4b5563;
}
.rule-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 600;
  flex-shrink: 0;
}
.rule-tag.primary { background: #dbeafe; color: #1d4ed8; }
.rule-tag.success { background: #d1fae5; color: #047857; }
.strategy-tip { margin: 16px 0; }
.estimate-summary {
  margin: 12px 0;
  padding: 12px 16px;
  background: #f0f9ff;
  border-radius: 8px;
  border: 1px solid #bae6fd;
}
.estimate-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.9rem;
  color: #1e3a5f;
  padding: 4px 0;
}
.estimate-row strong {
  color: #1e40af;
}
.estimate-row.highlight {
  margin-top: 6px;
  padding-top: 8px;
  border-top: 1px dashed #93c5fd;
  color: #059669;
  font-weight: 600;
}
.eval-high { color: #059669; font-weight: 600; }
.eval-mid { color: #d97706; font-weight: 600; }
.eval-low { color: #9ca3af; }
</style>
