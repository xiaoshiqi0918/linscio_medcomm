<template>
  <div class="article-editor">
    <div class="editor-header">
      <div class="title-edit-row">
        <el-input
          v-model="articleTitleDraft"
          class="article-title-input"
          placeholder="文章标题（导出在篇首；全文完成后可点「AI 总结标题」）"
          clearable
          @change="saveArticleTitle"
        />
        <el-button size="small" :loading="titleGenerating" @click="handleGenerateTitle">
          AI 总结标题
        </el-button>
      </div>
      <p v-if="article?.topic" class="topic-hint">主题：{{ article.topic }}</p>
      <div class="tags">
        <FormatBadge :format-id="article?.content_format || 'article'" />
        <PlatformBadge v-if="article?.platform" :platform-id="article.platform" />
      </div>
      <StageProgressBar
        :current-stage="article?.current_stage"
        :image-stage="article?.image_stage"
      />
    </div>
    <div class="toolbar">
      <el-dropdown trigger="click" @command="handleExport">
        <el-button size="small">导出</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="html">HTML</el-dropdown-item>
            <el-dropdown-item command="md">Markdown</el-dropdown-item>
            <el-dropdown-item command="docx">DOCX</el-dropdown-item>
            <el-dropdown-item command="pdf">PDF</el-dropdown-item>
            <el-dropdown-item command="txt">TXT</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-button size="small" :loading="copyMdLoading" @click="copyMarkdownExport">复制 Markdown</el-button>
      <el-dropdown trigger="click">
        <el-button size="small">
          写作辅助
          <el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="router.push('/personal-corpus')">个人语料</el-dropdown-item>
            <el-dropdown-item divided @click="router.push('/polish')">润色（实验页）</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-button
        type="primary"
        size="small"
        :loading="generating"
        :disabled="!currentSectionId"
        @click="handleGenerate"
      >
        AI 生成
      </el-button>
    </div>
    <div v-if="article?.sections?.length" class="section-tabs">
      <el-radio-group v-model="currentSectionId" size="small" @change="onSectionChange">
        <el-radio-button
          v-for="s in article.sections"
          :key="s.id"
          :value="s.id"
        >{{ s.title || s.section_type }}</el-radio-button>
      </el-radio-group>
    </div>
    <el-collapse class="bindings-panel">
      <el-collapse-item name="refs">
        <template #title>
          <span>参考文献绑定</span>
          <el-tag v-if="bindings.length" size="small" type="info" style="margin-left: 0.5rem;">{{ bindings.length }} 篇</el-tag>
        </template>
        <div class="bindings-content">
          <div class="bindings-toolbar">
            <el-radio-group v-model="bindingScope" size="small">
              <el-radio-button :value="'section'">当前章节</el-radio-button>
              <el-radio-button :value="'article'">整篇文章</el-radio-button>
            </el-radio-group>
            <div class="bindings-toolbar-actions">
              <el-button size="small" @click="showBindDialog = true">添加文献</el-button>
              <el-button size="small" type="primary" plain @click="showExternalSearchDialog = true">
                检索支撑文献
              </el-button>
            </div>
          </div>
          <ul v-if="bindings.length" class="bindings-list">
            <li v-for="b in indexedBindings" :key="b.binding_id" class="binding-item">
              <span class="binding-title">
                [{{ b.refIndex }}] {{ b.title }}
                <el-tag v-if="b._kind === 'external'" size="small" type="info" style="margin-left: 6px;">外部</el-tag>
              </span>
              <span class="binding-actions">
                <el-button type="primary" link size="small" @click="insertCitation(b)">插入</el-button>
                <el-button v-if="b._kind === 'local'" type="success" link size="small" @click="openPaperDetail(b.paper_id)">查看</el-button>
                <el-button v-else type="success" link size="small" @click="showExternalRefDetail(b)">查看</el-button>
                <el-button v-if="b._kind === 'local'" type="danger" link size="small" @click="removeBinding(b.binding_id)">移除</el-button>
                <el-button v-else type="danger" link size="small" @click="removeExternalRef(b.ref_id)">移除</el-button>
              </span>
            </li>
          </ul>
          <div v-else class="bindings-empty">暂无绑定文献</div>
        </div>
      </el-collapse-item>
      <el-collapse-item name="versions">
        <template #title>
          <span>版本与快照</span>
          <el-tag v-if="articleSnapshots.length" size="small" type="info" style="margin-left: 0.5rem;">{{ articleSnapshots.length }} 快照</el-tag>
        </template>
        <div class="version-snap-panel">
          <p class="vs-hint">章节每次保存会滚动保留最近约 30 个版本；整篇快照由你手动打点，便于大改前备份。</p>
          <div v-if="currentSectionId" class="vs-block">
            <div class="vs-label">当前章节版本</div>
            <el-button size="small" @click="fetchSectionVersions" :loading="versionsLoading">刷新列表</el-button>
            <el-table :data="sectionVersions" size="small" max-height="200" style="margin-top: 8px">
              <el-table-column prop="version" label="#" width="56" />
              <el-table-column prop="version_type" label="类型" width="120" />
              <el-table-column prop="created_at" label="时间" min-width="160" />
              <el-table-column label="" width="100" fixed="right">
                <template #default="{ row }">
                  <el-button v-if="!row.is_current" type="primary" link size="small" @click="revertToVersion(row)">恢复</el-button>
                  <el-tag v-else size="small">当前</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <div class="vs-block">
            <div class="vs-label">整篇文章快照</div>
            <div class="vs-row">
              <el-input v-model="snapshotLabel" placeholder="快照名称（可选）" size="small" clearable style="max-width: 240px" />
              <el-button size="small" type="primary" :loading="snapshotSaving" @click="createArticleSnapshot">保存快照</el-button>
              <el-button size="small" @click="fetchSnapshots" :loading="snapshotsLoading">刷新</el-button>
            </div>
            <el-table :data="articleSnapshots" size="small" max-height="220" style="margin-top: 8px">
              <el-table-column prop="label" label="名称" min-width="120" show-overflow-tooltip />
              <el-table-column prop="created_at" label="时间" min-width="160" />
              <el-table-column label="" width="150" fixed="right">
                <template #default="{ row }">
                  <el-button type="primary" link size="small" @click="restoreSnapshot(row)">恢复</el-button>
                  <el-button type="danger" link size="small" @click="deleteSnapshot(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-collapse-item>
      <el-collapse-item name="verify">
        <template #title>
          <span>本节核实与依据</span>
          <el-tag
            v-if="sectionVerifyReport?.claims && !sectionVerifyReport.claims.skipped"
            size="small"
            type="success"
            style="margin-left: 0.5rem;"
          >
            {{ sectionVerifyReport.claims.verified_count ?? 0 }} 已匹配
          </el-tag>
        </template>
        <VerificationPanel v-if="sectionVerifyReport" :report="sectionVerifyReport" />
        <p v-else class="verify-empty-hint">
          保存或 AI 生成本节后，此处会显示声明核对与文献片段；也可在右侧「核实状态」查看。
        </p>
      </el-collapse-item>
    </el-collapse>
    <el-dialog v-model="showBindDialog" title="添加参考文献" width="520px">
      <el-input v-model="bindSearchQ" placeholder="搜索文献（回车搜索）" clearable style="margin-bottom: 0.5rem;" @keyup.enter="searchPapersForBind" />
      <el-table
        :data="papersForBind"
        :row-key="(r: any) => r.id"
        max-height="260"
        highlight-current-row
        @selection-change="onPaperSelectionChange"
      >
        <el-table-column type="selection" width="40" />
        <el-table-column prop="title" label="标题" show-overflow-tooltip min-width="200" />
        <el-table-column label="全文" width="88" align="center">
          <template #default="{ row }">
            <el-tag :type="bindFulltextTagType(row.fulltext_status)" size="small">
              {{ bindFulltextLabel(row.fulltext_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="year" label="年份" width="70" />
      </el-table>
      <template #footer>
        <el-button @click="showBindDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedPaperIds.length" @click="confirmBind">添加</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="showExternalSearchDialog" title="检索支撑文献（PubMed/CrossRef）" width="860px">
      <div class="translate-assist-bar">
        <span class="translate-assist-label">中译英辅助</span>
        <el-input
          v-model="translateInput"
          placeholder="输入中文关键词，如：糖尿病"
          style="width: 220px;"
          size="small"
          @keyup.enter="doTranslateKeyword"
        />
        <el-button size="small" type="primary" plain :loading="translateLoading" @click="doTranslateKeyword">翻译</el-button>
        <template v-if="translateOutput">
          <span class="translate-assist-result">{{ translateOutput }}</span>
          <el-button size="small" @click="useTranslateResult">用作关键词</el-button>
          <el-button size="small" text @click="appendTranslateResult">追加到关键词</el-button>
        </template>
        <span class="translate-assist-tip">PubMed 仅支持英文检索</span>
      </div>
      <el-form inline>
        <el-form-item label="关键词">
          <el-input v-model="externalQuery" placeholder="自动带入文章主题，可自行修改" style="width: 320px;" @keyup.enter="doExternalSearchForArticle" />
          <el-tooltip placement="top-start" effect="dark">
            <template #content>
              <div style="max-width: 420px; line-height: 1.6;">
                <div style="font-weight: 600; margin-bottom: 4px;">PubMed 高级语法支持：</div>
                <div>关键词[ti] -> 限定标题字段</div>
                <div>关键词[tiab] -> 标题+摘要字段</div>
                <div>糖尿病[MeSH] -> MeSH 受控词</div>
                <div>AND / OR / NOT -> 布尔逻辑</div>
                <div>"精确短语"[tiab] -> 短语检索</div>
                <div style="margin-top: 6px;">示例：metformin[ti] AND diabetes[MeSH] AND 2020:2024[dp]</div>
              </div>
            </template>
            <el-button link type="info" style="margin-left: 6px;">语法说明</el-button>
          </el-tooltip>
        </el-form-item>
        <el-form-item label="数据源">
          <el-checkbox-group v-model="externalSources">
            <el-checkbox value="pubmed">PubMed</el-checkbox>
            <el-checkbox value="crossref">CrossRef</el-checkbox>
            <el-checkbox value="semantic_scholar">Semantic Scholar</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="年份">
          <el-input-number v-model="externalYearFrom" :min="1900" :max="2099" placeholder="起始" />
          <span style="margin: 0 6px;">至</span>
          <el-input-number v-model="externalYearTo" :min="1900" :max="2099" placeholder="结束" />
        </el-form-item>
        <el-form-item label="语言">
          <el-select v-model="externalLanguage" style="width: 120px;">
            <el-option label="全部" value="all" />
            <el-option label="英文" value="en" />
            <el-option label="中文" value="zh" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="externalSearching" @click="doExternalSearchForArticle">检索</el-button>
          <el-dropdown trigger="click" @command="onApiKeyCommand" style="margin-left: 8px;">
            <el-button>API Key 配置 <el-icon class="el-icon--right"><arrow-down /></el-icon></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="configNcbi">配置 NCBI Key（PubMed）</el-dropdown-item>
                <el-dropdown-item command="applyNcbi">申请 NCBI API Key ↗</el-dropdown-item>
                <el-dropdown-item command="configS2" divided>配置 Semantic Scholar Key</el-dropdown-item>
                <el-dropdown-item command="applyS2">申请 S2 API Key ↗</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </el-form-item>
      </el-form>
      <div class="external-search-filters">
        <el-switch v-model="onlyUnboundExternal" active-text="仅未绑定" inactive-text="全部" />
        <el-select v-model="externalTypeFilter" placeholder="文献类型" clearable style="width: 160px;">
          <el-option label="指南" value="guideline" />
          <el-option label="综述" value="review" />
          <el-option label="Meta分析" value="meta" />
          <el-option label="临床试验" value="rct" />
        </el-select>
        <el-checkbox-group v-model="externalPubTypes">
          <el-checkbox value="guideline">指南</el-checkbox>
          <el-checkbox value="review">综述</el-checkbox>
          <el-checkbox value="meta">Meta分析</el-checkbox>
          <el-checkbox value="rct">临床试验</el-checkbox>
        </el-checkbox-group>
        <el-select v-model="externalSortBy" style="width: 140px;">
          <el-option label="年份降序" value="year_desc" />
          <el-option label="年份升序" value="year_asc" />
          <el-option label="标题A-Z" value="title_asc" />
        </el-select>
      </div>
      <div v-if="externalPolicyText" style="margin: 6px 0 2px; color: #6b7280; font-size: 12px;">
        语言策略：{{ externalPolicyText }}
      </div>
      <div v-if="externalSourceStats.length" class="source-stats-row">
        <div v-for="s in externalSourceStats" :key="s.id" class="source-stat-card">
          <div class="source-stat-title">{{ s.id }}</div>
          <div class="source-stat-line">
            <el-progress :percentage="Math.round(s.progress || 0)" :stroke-width="6" :show-text="false" />
            <span>{{ Math.round(s.progress || 0) }}%</span>
          </div>
          <div class="source-stat-line">阶段：{{ s.stageText || '检索中' }}</div>
          <div class="source-stat-line">结果：{{ s.count }}</div>
          <div class="source-stat-line">耗时：{{ s.elapsed }}ms</div>
          <div v-if="s.error" class="source-stat-error">异常：{{ s.error }}</div>
          <div v-else-if="s.status === 'done'" class="source-stat-ok">完成</div>
          <div v-else class="source-stat-line">进行中</div>
        </div>
      </div>
      <div v-if="externalHistory.length" class="external-history">
        <span class="external-history-title">最近检索：</span>
        <el-select v-model="pinnedGroupFilter" clearable placeholder="按分组筛选置顶" size="small" style="width: 170px;">
          <el-option v-for="g in pinnedGroupOptions" :key="g" :label="g" :value="g" />
        </el-select>
        <el-button size="small" @click="exportPinnedConfig">导出置顶配置</el-button>
        <el-button size="small" @click="importPinnedConfig">导入置顶配置</el-button>
        <el-button size="small" type="warning" :disabled="!hasPinnedBackup" @click="rollbackPinnedBackup">回滚上次导入</el-button>
        <span
          v-for="h in displayExternalHistory"
          :key="h.id"
          class="external-history-chip"
          :draggable="isHistoryPinned(h.query)"
          @dragstart="onHistoryDragStart(h.query)"
          @dragover.prevent="onHistoryDragOver(h.query)"
          @drop.prevent="onHistoryDrop(h.query)"
        >
          <el-tag class="external-history-item" @click="applyHistoryAndSearch(h)">
            <span v-if="isHistoryPinned(h.query)">★</span>{{ historyDisplayName(h.query) }}
          </el-tag>
          <el-button
            v-if="isHistoryPinned(h.query)"
            link
            type="primary"
            size="small"
            class="external-history-rename"
            @click.stop="renamePinnedHistory(h.query)"
          >
            重命名
          </el-button>
          <el-button
            v-if="isHistoryPinned(h.query)"
            link
            type="info"
            size="small"
            class="external-history-group"
            @click.stop="setPinnedGroup(h.query)"
          >
            分组
          </el-button>
          <el-button link type="warning" size="small" class="external-history-pin" @click.stop="togglePinHistory(h.query)">
            {{ isHistoryPinned(h.query) ? '取消置顶' : '置顶' }}
          </el-button>
          <el-button link type="danger" size="small" class="external-history-del" @click.stop="deleteHistoryItem(h.id)">x</el-button>
        </span>
      </div>
      <el-tabs v-model="externalGroupTab" class="external-group-tabs">
        <el-tab-pane :label="`全部(${externalGroupCounts.all})`" name="all" />
        <el-tab-pane :label="`指南(${externalGroupCounts.guideline})`" name="guideline" />
        <el-tab-pane :label="`综述(${externalGroupCounts.review})`" name="review" />
        <el-tab-pane :label="`Meta分析(${externalGroupCounts.meta})`" name="meta" />
        <el-tab-pane :label="`临床试验(${externalGroupCounts.rct})`" name="rct" />
      </el-tabs>
      <el-table :data="filteredExternalResults" max-height="380" @selection-change="onExternalSelectionChange">
        <el-table-column type="selection" width="40" />
        <el-table-column prop="title" label="标题" min-width="280" show-overflow-tooltip />
        <el-table-column prop="year" label="年份" width="80" />
        <el-table-column label="来源" width="120">
          <template #default="{ row }">{{ (row._sources || [row.source]).join(',') }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.local_status === 'saved' ? 'success' : 'info'">
              {{ row.local_status === 'saved' ? '已入库' : '未入库' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="showExternalSearchDialog = false">关闭</el-button>
        <el-button type="primary" :disabled="!externalSelectedRows.length" :loading="externalBinding" @click="saveAndBindExternalSelected">
          入库并绑定
        </el-button>
        <el-button type="success" plain :disabled="!externalSelectedRows.length" :loading="externalBinding" @click="bindExternalSelectedNoSave">
          直接绑定（不入库）
        </el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="showExternalRefDialog" title="外部引用详情" width="640px">
      <div v-if="activeExternalRef">
        <div style="font-weight: 600; margin-bottom: 6px;">{{ activeExternalRef.title }}</div>
        <div style="color: #6b7280; margin-bottom: 8px;">
          {{ (activeExternalRef.authors || []).map((a: any) => a.name).join('; ') || '-' }}
          · {{ activeExternalRef.journal || '-' }}
          · {{ activeExternalRef.year || '-' }}
        </div>
        <div v-if="activeExternalRef.doi">DOI: {{ activeExternalRef.doi }}</div>
        <div v-if="activeExternalRef.pmid">PMID: {{ activeExternalRef.pmid }}</div>
        <div v-if="activeExternalRef.url" style="margin-top: 6px;">
          <el-button link type="primary" @click="openExternalUrl(activeExternalRef.url)">打开链接</el-button>
        </div>
        <div v-if="activeExternalRef.abstract" class="panel-text" style="margin-top: 10px;">
          {{ activeExternalRef.abstract }}
        </div>
      </div>
      <template #footer>
        <el-button @click="showExternalRefDialog = false">关闭</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="showImportOptionsDialog" title="选择导入内容" width="420px">
      <el-checkbox-group v-model="importDimensions">
        <el-checkbox value="pinned">置顶词</el-checkbox>
        <el-checkbox value="alias">别名</el-checkbox>
        <el-checkbox value="group">分组</el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="showImportOptionsDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmImportWithDimensions">继续导入</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="showRollbackDialog" title="选择回滚备份" width="520px">
      <el-radio-group v-model="selectedRollbackId" class="rollback-list">
        <div v-for="b in pinnedBackups" :key="b.id" class="rollback-item">
          <el-radio :value="b.id">
            {{ new Date(b.saved_at).toLocaleString() }}（置顶 {{ b.pinned?.length || 0 }} 条）
          </el-radio>
          <el-button link type="danger" size="small" @click.stop="deletePinnedBackup(b.id)">删除</el-button>
        </div>
      </el-radio-group>
      <template #footer>
        <el-button type="danger" plain :disabled="!pinnedBackups.length" @click="clearAllPinnedBackups">清空备份</el-button>
        <el-button @click="showRollbackDialog = false">取消</el-button>
        <el-button type="warning" :disabled="!selectedRollbackId" @click="confirmRollbackBySelection">回滚</el-button>
      </template>
    </el-dialog>
    <div v-if="streamedText" class="stream-preview">
      {{ streamedText }}
    </div>
    <el-collapse v-if="showSeriesVisualPanel" class="series-visual-collapse">
      <el-collapse-item title="图示连贯性（条漫 / 分镜 / 卡片系列）" name="series-visual">
        <p class="series-visual-hint">
          锁定文案会注入每一张生成图的正向提示词；系列种子基准在 ComfyUI 等支持种子的后端下可区分各格随机性。像素级一致需工作流内参考图 / LoRA。
        </p>
        <el-input
          v-model="visualContinuityDraft"
          type="textarea"
          :rows="4"
          placeholder="例如：同一角色形象与配色、线条风格、禁止写实照片…（中/英均可）"
        />
        <div class="series-seed-row">
          <span class="series-seed-label">系列种子基准（留空则各格随机）</span>
          <el-input-number
            v-model="imageSeriesSeedBaseDraft"
            :min="0"
            :max="2147483647"
            :step="1"
            controls-position="right"
            placeholder="可选"
          />
        </div>
        <el-button type="primary" size="small" :loading="savingVisualContinuity" @click="saveVisualContinuity">
          保存到文章
        </el-button>
      </el-collapse-item>
    </el-collapse>
    <div class="editor-area">
      <MedCommEditor
        v-if="article"
        ref="editorRef"
        :key="`${articleId}-${currentSectionId}`"
        :model-value="contentJson"
        :locate-request="locateRequest"
        :article-id="articleId"
        @update:model-value="onContentUpdate"
        @locate-result="onEditorLocateResult"
        @citation-click="onCitationClick"
        @claim-click="onMedClaimClick"
        :content-format="article.content_format"
      />
    </div>

    <el-dialog
      v-model="exportCheckDialogVisible"
      title="导出前检查"
      width="640px"
      destroy-on-close
    >
      <div class="export-check-summary">{{ exportCheckMessage }}</div>
      <div v-if="exportDataWarnings.length" class="export-check-group">
        <div class="export-check-title">[DATA:] 占位符</div>
        <div v-for="(item, idx) in exportDataWarnings" :key="`dw-${idx}`" class="export-check-item">
          <span class="export-check-text">{{ item.text }}</span>
          <el-button size="small" text type="primary" @click="locateIssueText(item.text)">定位</el-button>
        </div>
      </div>
      <div v-if="exportAbsoluteTerms.length" class="export-check-group">
        <div class="export-check-title">绝对化表述</div>
        <div v-for="(item, idx) in exportAbsoluteTerms" :key="`at-${idx}`" class="export-check-item">
          <span class="export-check-text">{{ item.text }}</span>
          <el-button size="small" text type="primary" @click="locateIssueText(item.text)">定位</el-button>
        </div>
      </div>
      <div v-if="exportOrphanCitations.length" class="export-check-group">
        <div class="export-check-title">孤儿引用（文献已移除绑定）</div>
        <div v-for="(item, idx) in exportOrphanCitations" :key="`oc-${idx}`" class="export-check-item">
          <span class="export-check-text">{{ item.section_title }}：{{ item.text }}</span>
          <span>
            <el-button size="small" text type="primary" @click="locateOrphanCitation(item)">定位</el-button>
          </span>
        </div>
        <el-button size="small" type="primary" @click="removeOrphanCitations">移除孤儿引用</el-button>
      </div>
      <template #footer>
        <el-button @click="exportCheckDialogVisible = false">取消</el-button>
        <el-button type="warning" @click="confirmExportWithWarnings">仍要导出</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="claimEvidenceVisible" title="依据核对" width="540px" destroy-on-close>
      <div v-if="claimEvidencePayload" class="claim-evidence-body">
        <p v-if="claimEvidencePayload.text" class="ce-row">
          <span class="ce-label">句段</span>
          <span>{{ claimEvidencePayload.text }}</span>
        </p>
        <p v-if="claimEvidencePayload.evidenceSource" class="ce-row">
          <span class="ce-label">来源</span>
          <span>{{ claimEvidencePayload.evidenceSource }}</span>
        </p>
        <p v-if="claimEvidencePayload.chunkId" class="ce-row">
          <span class="ce-label">Chunk</span>
          <span>{{ claimEvidencePayload.chunkId }}</span>
        </p>
        <div class="ce-snippet">{{ claimEvidencePayload.evidenceSnippet || '（无片段，可打开文献全文对照）' }}</div>
      </div>
      <template #footer>
        <el-button @click="claimEvidenceVisible = false">关闭</el-button>
        <el-button v-if="claimEvidencePayload?.paperId" type="primary" @click="openPaperFromClaimEvidence">
          打开文献
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MedCommEditor from '@/components/editor/MedCommEditor.vue'
import VerificationPanel from '@/components/verification/VerificationPanel.vue'
import FormatBadge from '@/components/common/FormatBadge.vue'
import PlatformBadge from '@/components/common/PlatformBadge.vue'
import StageProgressBar from '@/components/layout/StageProgressBar.vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, axiosErrorDetail, API_BASE, getAuthToken, getLocalApiKeyHeaderForFetch } from '@/api'
import { useStreamGenerate } from '@/composables/useStreamGenerate'
import { useArticleStore } from '@/stores/article'
import { AUTH_USER_CHANGED_EVENT } from '@/stores/auth'
import { extractPlainFromTiptapJson, stripOrphanCitationMarks } from '@/utils/tiptapPlainText'

const route = useRoute()
const router = useRouter()
const articleStore = useArticleStore()
const article = ref<any>(null)
const articleTitleDraft = ref('')
const titleGenerating = ref(false)
const copyMdLoading = ref(false)
const claimEvidenceVisible = ref(false)
const claimEvidencePayload = ref<{
  paperId: number
  evidenceSnippet: string
  evidenceSource: string
  chunkId: string
  text: string
} | null>(null)
const contentJson = ref<any>(null)
const visualContinuityDraft = ref('')
const imageSeriesSeedBaseDraft = ref<number | null>(null)
const savingVisualContinuity = ref(false)

const showSeriesVisualPanel = computed(() => {
  const cf = article.value?.content_format
  return cf === 'comic_strip' || cf === 'storyboard' || cf === 'card_series'
})

const sectionVerifyReport = computed(() => article.value?.verify_report ?? articleStore.verificationReport)

const currentSectionId = ref<number | null>(null)
const { generating, streamedText, generateSection } = useStreamGenerate()
const exportCheckDialogVisible = ref(false)
const exportCheckMessage = ref('')
const exportDataWarnings = ref<Array<{ text: string; message?: string }>>([])
const exportAbsoluteTerms = ref<Array<{ text: string; suggestion?: string }>>([])
const exportOrphanCitations = ref<Array<{ section_id: number; section_title: string; text: string; paper_id: number }>>([])
const exportValidPaperIds = ref<number[]>([])
const pendingExportFormat = ref<string | null>(null)
const locateRequest = ref<{ text: string; token: number } | null>(null)
const locateToken = ref(0)
/** 为 true 时，下一次子组件 locate-result 用于提示用户 */
const awaitLocateFeedback = ref(false)

const bindings = ref<any[]>([])
const externalRefs = ref<any[]>([])
const bindingScope = ref<'section' | 'article'>('section')
const showBindDialog = ref(false)
const papersForBind = ref<any[]>([])
const bindSearchQ = ref('')
const selectedPaperIds = ref<number[]>([])
const editorRef = ref<any>(null)
const showExternalSearchDialog = ref(false)
const externalQuery = ref('')
const externalSources = ref<Array<'pubmed' | 'crossref' | 'semantic_scholar'>>(['pubmed', 'crossref'])
const externalSearching = ref(false)
const translateInput = ref('')
const translateOutput = ref('')
const translateLoading = ref(false)
const externalResults = ref<any[]>([])
const externalSelectedRows = ref<any[]>([])
const externalBinding = ref(false)
const externalPolicyText = ref('')
const externalSourceStats = ref<Array<{ id: string; count: number; elapsed: number; error?: string; progress: number; status: 'running' | 'done' | 'error'; stageText?: string }>>([])
let externalProgressTimer: number | null = null
const externalYearFrom = ref<number | null>(null)
const externalYearTo = ref<number | null>(null)
const externalLanguage = ref<'all' | 'en' | 'zh'>('all')
const externalPubTypes = ref<Array<'guideline' | 'review' | 'meta' | 'rct'>>([])
const showExternalRefDialog = ref(false)
const activeExternalRef = ref<any>(null)
const externalHistory = ref<Array<{ id: number; query: string; sources: string[]; filters: any }>>([])
const PINNED_HISTORY_KEY = 'medcomm_external_search_pinned_v1'
const PINNED_HISTORY_ALIAS_KEY = 'medcomm_external_search_pinned_alias_v1'
const PINNED_HISTORY_GROUP_KEY = 'medcomm_external_search_pinned_group_v1'
const PINNED_HISTORY_BACKUP_KEY = 'medcomm_external_search_pinned_backup_v1'
const PINNED_HISTORY_BACKUPS_KEY = 'medcomm_external_search_pinned_backups_v1'
const PINNED_CONFIG_VERSION = 1
const pinnedHistory = ref<string[]>([])
const pinnedHistoryAlias = ref<Record<string, string>>({})
const pinnedHistoryGroup = ref<Record<string, string>>({})
const pinnedGroupFilter = ref('')
const historyDragFrom = ref('')
const hasPinnedBackup = ref(false)
const pinnedBackups = ref<Array<{ id: string; saved_at: string; pinned: string[]; alias: Record<string, string>; group: Record<string, string> }>>([])
const showImportOptionsDialog = ref(false)
const importDimensions = ref<Array<'pinned' | 'alias' | 'group'>>(['pinned', 'alias', 'group'])
const pendingImportConfig = ref<any>(null)
const showRollbackDialog = ref(false)
const selectedRollbackId = ref('')
const onlyUnboundExternal = ref(false)
const externalTypeFilter = ref<'guideline' | 'review' | 'meta' | 'rct' | ''>('')
const externalSortBy = ref<'year_desc' | 'year_asc' | 'title_asc'>('year_desc')
const externalGroupTab = ref<'all' | 'guideline' | 'review' | 'meta' | 'rct'>('all')

const articleId = computed(() => Number(route.params.id))

const sectionVersions = ref<Array<{ id: number; version: number; version_type: string; is_current: boolean; created_at: string | null }>>([])
const versionsLoading = ref(false)
const articleSnapshots = ref<Array<{ id: number; label: string; created_at: string | null }>>([])
const snapshotsLoading = ref(false)
const snapshotSaving = ref(false)
const snapshotLabel = ref('')

async function fetchSectionVersions() {
  if (!currentSectionId.value) return
  versionsLoading.value = true
  try {
    const res = await api.medcomm.getSectionVersions(currentSectionId.value)
    sectionVersions.value = res.data?.items || []
  } catch (e: any) {
    ElMessage.error(axiosErrorDetail(e) || '加载版本失败')
  } finally {
    versionsLoading.value = false
  }
}

async function revertToVersion(row: { id: number }) {
  if (!currentSectionId.value) return
  try {
    await api.medcomm.revertSection(currentSectionId.value, row.id)
    ElMessage.success('已恢复到该版本')
    await loadArticle(currentSectionId.value ?? undefined)
  } catch (e: any) {
    ElMessage.error(axiosErrorDetail(e) || '恢复失败')
  }
}

async function fetchSnapshots() {
  if (!articleId.value) return
  snapshotsLoading.value = true
  try {
    const res = await api.medcomm.listSnapshots(articleId.value)
    articleSnapshots.value = res.data?.items || []
  } catch (e: any) {
    ElMessage.error(axiosErrorDetail(e) || '加载快照失败')
  } finally {
    snapshotsLoading.value = false
  }
}

async function createArticleSnapshot() {
  if (!articleId.value) return
  snapshotSaving.value = true
  try {
    await api.medcomm.createSnapshot(articleId.value, { label: snapshotLabel.value.trim() })
    snapshotLabel.value = ''
    ElMessage.success('快照已保存')
    await fetchSnapshots()
  } catch (e: any) {
    ElMessage.error(axiosErrorDetail(e) || '保存快照失败')
  } finally {
    snapshotSaving.value = false
  }
}

async function restoreSnapshot(row: { id: number }) {
  if (!articleId.value) return
  try {
    await ElMessageBox.confirm('将从快照恢复所有章节当前平台下的内容，并产生新版本。是否继续？', '恢复快照', {
      type: 'warning',
      confirmButtonText: '恢复',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await api.medcomm.restoreSnapshot(articleId.value, row.id)
    ElMessage.success('已从快照恢复')
    await loadArticle(currentSectionId.value ?? undefined)
    await fetchSectionVersions()
    await fetchSnapshots()
  } catch (e: any) {
    ElMessage.error(axiosErrorDetail(e) || '恢复失败')
  }
}

async function deleteSnapshot(row: { id: number }) {
  if (!articleId.value) return
  try {
    await api.medcomm.deleteSnapshot(articleId.value, row.id)
    ElMessage.success('已删除')
    await fetchSnapshots()
  } catch (e: any) {
    ElMessage.error(axiosErrorDetail(e) || '删除失败')
  }
}

watch(currentSectionId, () => {
  sectionVersions.value = []
})

const indexedBindings = computed(() => {
  const local = (bindings.value || []).map((b: any) => ({ ...b, _kind: 'local' as const }))
  const ext = (externalRefs.value || []).map((b: any) => ({
    ...b,
    _kind: 'external' as const,
    binding_id: `ext-${b.ref_id}`,
    paper_id: null,
  }))
  return [...local, ...ext].map((b: any, idx: number) => ({ ...b, refIndex: idx + 1 }))
})
const citationIndexMap = computed<Record<string, number>>(() => {
  const m: Record<string, number> = {}
  for (const b of indexedBindings.value) {
    const pid = Number(b.paper_id || 0)
    const idx = Number(b.refIndex || 0)
    if (pid && idx) m[String(pid)] = idx
  }
  return m
})
const boundPaperIdSet = computed(() => new Set((bindings.value || []).map((b: any) => Number(b.paper_id)).filter(Boolean)))
function classifyExternalType(r: any): 'guideline' | 'review' | 'meta' | 'rct' | 'other' {
  const t = ((r?.pub_types || []).join(' ') + ' ' + (r?.title || '')).toLowerCase()
  if (t.includes('guideline')) return 'guideline'
  if (t.includes('meta')) return 'meta'
  if (t.includes('review')) return 'review'
  if (t.includes('trial') || t.includes('randomized')) return 'rct'
  return 'other'
}
const externalGroupCounts = computed(() => {
  const rows = [...(externalResults.value || [])].filter((r: any) => {
    if (!onlyUnboundExternal.value) return true
    return !boundPaperIdSet.value.has(Number(r.local_id || r.paper_id || 0))
  })
  const c = { all: rows.length, guideline: 0, review: 0, meta: 0, rct: 0 }
  for (const r of rows) {
    const k = classifyExternalType(r)
    if (k !== 'other') c[k] += 1
  }
  return c
})
const pinnedGroupOptions = computed(() => {
  const s = new Set<string>()
  for (const q of pinnedHistory.value) {
    const g = (pinnedHistoryGroup.value[q] || '').trim()
    if (g) s.add(g)
  }
  return [...s]
})
const displayExternalHistory = computed(() => {
  const group = (pinnedGroupFilter.value || '').trim()
  if (!group) return externalHistory.value
  return externalHistory.value.filter((h) => {
    if (!isHistoryPinned(h.query)) return false
    return (pinnedHistoryGroup.value[h.query] || '').trim() === group
  })
})
const filteredExternalResults = computed(() => {
  let rows = [...(externalResults.value || [])]
  if (onlyUnboundExternal.value) {
    rows = rows.filter((r: any) => !boundPaperIdSet.value.has(Number(r.local_id || r.paper_id || 0)))
  }
  const typeKw = externalTypeFilter.value || (externalGroupTab.value === 'all' ? '' : externalGroupTab.value)
  if (typeKw) {
    const kw = typeKw
    rows = rows.filter((r: any) => classifyExternalType(r) === kw)
  }
  if (externalSortBy.value === 'year_asc') {
    rows.sort((a: any, b: any) => Number(a.year || 0) - Number(b.year || 0))
  } else if (externalSortBy.value === 'title_asc') {
    rows.sort((a: any, b: any) => String(a.title || '').localeCompare(String(b.title || '')))
  } else {
    rows.sort((a: any, b: any) => Number(b.year || 0) - Number(a.year || 0))
  }
  return rows
})

async function loadArticle(sectionId?: number) {
  if (!articleId.value) return
  try {
    const res = await api.medcomm.getArticle(articleId.value, sectionId ?? currentSectionId.value ?? undefined)
    article.value = res.data
    articleTitleDraft.value = (res.data?.title || '').trim()
    articleStore.setCurrent(res.data)
    articleStore.setVerificationReport(res.data?.verify_report ?? null)
    if (res.data?.current_section_id && !currentSectionId.value) {
      currentSectionId.value = res.data.current_section_id
    } else if (res.data?.sections?.[0] && !currentSectionId.value) {
      currentSectionId.value = res.data.sections[0].id
    }
    contentJson.value = res.data?.content_json || { type: 'doc', content: [] }
    visualContinuityDraft.value = res.data?.visual_continuity_prompt || ''
    imageSeriesSeedBaseDraft.value =
      res.data?.image_series_seed_base != null ? Number(res.data.image_series_seed_base) : null
    void fetchSnapshots()
  } catch {
    article.value = null
  }
}

async function saveVisualContinuity() {
  if (!articleId.value) return
  savingVisualContinuity.value = true
  try {
    const res = await api.medcomm.patchArticleVisualContinuity(articleId.value, {
      visual_continuity_prompt: visualContinuityDraft.value.trim(),
      image_series_seed_base: imageSeriesSeedBaseDraft.value,
    })
    if (res.data) {
      article.value = { ...article.value, ...res.data }
      articleStore.setCurrent(article.value)
    }
    ElMessage.success('已保存图示连贯性配置')
  } catch (e: any) {
    ElMessage.error(axiosErrorDetail(e) || '保存失败')
  } finally {
    savingVisualContinuity.value = false
  }
}

function onSectionChange() {
  loadArticle(currentSectionId.value ?? undefined)
  loadBindings()
}

function getSectionIdFromQuery(): number | null {
  const raw = route.query.section_id ?? route.query.sectionId
  const n = Number(raw)
  return Number.isFinite(n) && n > 0 ? n : null
}

async function loadBindings() {
  if (!articleId.value) return
  if (bindingScope.value === 'section' && !currentSectionId.value) {
    bindings.value = []
    externalRefs.value = []
    return
  }
  try {
    const params = bindingScope.value === 'section'
      ? { scope: 'section' as const, section_id: currentSectionId.value! }
      : { scope: 'article' as const }
    const [res, extRes] = await Promise.all([
      api.literature.getBindings(articleId.value, params),
      api.literature.getExternalRefs(articleId.value, params),
    ])
    bindings.value = res.data?.items || []
    externalRefs.value = extRes.data?.items || []
  } catch {
    bindings.value = []
    externalRefs.value = []
  }
}

function bindFulltextLabel(s: string | undefined) {
  if (s === 'full') return '就绪'
  if (s === 'no_fulltext') return '缺全文'
  return '获取中'
}

function bindFulltextTagType(s: string | undefined) {
  if (s === 'full') return 'success'
  if (s === 'no_fulltext') return 'danger'
  return 'warning'
}

async function searchPapersForBind() {
  try {
    const res = await api.literature.getPapers({ q: bindSearchQ.value || undefined, page_size: 30 })
    papersForBind.value = res.data?.items || []
  } catch {
    papersForBind.value = []
  }
}

function onPaperSelectionChange(rows: any[]) {
  selectedPaperIds.value = (rows || []).map((r: any) => r.id).filter(Boolean)
}

function onExternalSelectionChange(rows: any[]) {
  externalSelectedRows.value = rows || []
}

async function doTranslateKeyword() {
  const text = translateInput.value.trim()
  if (!text) {
    ElMessage.warning('请输入中文关键词')
    return
  }
  translateLoading.value = true
  translateOutput.value = ''
  try {
    const res = await api.translate.translate(text, 'en', 'zh')
    translateOutput.value = (res.data as any)?.text || ''
    if (!translateOutput.value) {
      ElMessage.warning('翻译结果为空，请重试')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '翻译失败')
  } finally {
    translateLoading.value = false
  }
}
function useTranslateResult() {
  if (translateOutput.value) {
    externalQuery.value = translateOutput.value
  }
}
function appendTranslateResult() {
  if (translateOutput.value) {
    const q = externalQuery.value.trim()
    externalQuery.value = q ? `${q} ${translateOutput.value}` : translateOutput.value
  }
}

async function doExternalSearchForArticle() {
  const q = externalQuery.value.trim() || String(article.value?.topic || article.value?.title || '').trim()
  if (!q) return
  if (!externalSources.value.length) return
  externalSearching.value = true
  externalSourceStats.value = externalSources.value.map((s) => ({
    id: s,
    count: 0,
    elapsed: 0,
    error: '',
    progress: 6,
    status: 'running',
    stageText: '初始化',
  }))
  if (externalProgressTimer) window.clearInterval(externalProgressTimer)
  externalProgressTimer = window.setInterval(() => {
    externalSourceStats.value = externalSourceStats.value.map((x) => (
      x.status === 'running' ? { ...x, progress: Math.min(90, x.progress + 8) } : x
    ))
  }, 400)
  try {
    const payload = {
      query: q,
      sources: externalSources.value,
      year_from: externalYearFrom.value || undefined,
      year_to: externalYearTo.value || undefined,
      pub_types: externalPubTypes.value.length ? externalPubTypes.value : undefined,
      language: externalLanguage.value,
      max_per_source: 20,
    }
    const token = getAuthToken()
    let finalData: any = null
    try {
      const localApiHeader = await getLocalApiKeyHeaderForFetch()
      if (!localApiHeader['X-Local-Api-Key']) throw new Error('NO_LOCAL_API_KEY_FOR_STREAM')
      const abortCtrl = new AbortController()
      let streamTimeout = window.setTimeout(() => abortCtrl.abort(), 20000)
      const refreshStreamTimeout = () => {
        window.clearTimeout(streamTimeout)
        streamTimeout = window.setTimeout(() => abortCtrl.abort(), 20000)
      }
      const resp = await fetch(`${API_BASE}/api/v1/literature/search/stream`, {
        method: 'POST',
        signal: abortCtrl.signal,
        headers: {
          'Content-Type': 'application/json',
          ...localApiHeader,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      })
      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`)
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const chunks = buf.split('\n\n')
        buf = chunks.pop() || ''
        for (const chunk of chunks) {
          const line = chunk.split('\n').find((l) => l.startsWith('data: '))
          if (!line) continue
          refreshStreamTimeout()
          const ev = JSON.parse(line.slice(6))
          if (ev?.type === 'source_done') {
            const p = ev.payload || {}
            const idx = externalSourceStats.value.findIndex((x) => x.id === p.source)
            const v = {
              id: String(p.source || ''),
              count: Number(p.count || 0),
              elapsed: Number(p.elapsed || 0),
              error: p.error || '',
              progress: 100,
              status: (p.error ? 'error' : 'done') as 'running' | 'done' | 'error',
              stageText: p.error ? '异常' : '完成',
            }
            if (idx >= 0) externalSourceStats.value[idx] = v
            else externalSourceStats.value.push(v)
          } else if (ev?.type === 'source_start') {
            const p = ev.payload || {}
            const idx = externalSourceStats.value.findIndex((x) => x.id === p.source)
            const v = {
              id: String(p.source || ''),
              count: 0,
              elapsed: 0,
              error: '',
              progress: 12,
              status: 'running' as const,
              stageText: '检索中',
            }
            if (idx >= 0) externalSourceStats.value[idx] = { ...externalSourceStats.value[idx], ...v }
            else externalSourceStats.value.push(v)
          } else if (ev?.type === 'source_stage') {
            const p = ev.payload || {}
            const idx = externalSourceStats.value.findIndex((x) => x.id === p.source)
            if (idx >= 0) {
              externalSourceStats.value[idx] = {
                ...externalSourceStats.value[idx],
                stageText: String(p.stage || '检索中'),
                progress: Math.max(externalSourceStats.value[idx].progress, Number(p.progress || 0)),
              }
            }
          } else if (ev?.type === 'final' || ev?.type === 'cached') {
            finalData = ev.payload
          }
        }
      }
      window.clearTimeout(streamTimeout)
      if (!finalData) throw new Error('STREAM_NO_FINAL')
    } catch {
      const res = await api.literature.searchExternal(payload)
      finalData = res.data
    }
    externalResults.value = finalData?.results || []
    const src = finalData?.sources || {}
    if (!externalSourceStats.value.length) {
      externalSourceStats.value = Object.keys(src).map((k) => ({
        id: k,
        count: Number(src[k]?.count || 0),
        elapsed: Number(src[k]?.elapsed || 0),
        error: src[k]?.error || '',
        progress: 100,
        status: (src[k]?.error ? 'error' : 'done') as 'running' | 'done' | 'error',
        stageText: src[k]?.error ? '异常' : '完成',
      }))
    }
    const policyMap: Record<string, string> = {
      query_tag: '查询标签',
      metadata: '元数据',
      heuristic: '启发式',
      none: '无',
    }
    externalPolicyText.value = externalLanguage.value === 'all'
      ? ''
      : Object.keys(src).map((k) => `${k}:${policyMap[src[k]?.language_policy || 'none']}`).join('，')
  } catch {
    externalResults.value = []
    externalPolicyText.value = ''
    externalSourceStats.value = []
  } finally {
    if (externalProgressTimer) {
      window.clearInterval(externalProgressTimer)
      externalProgressTimer = null
    }
    externalSearching.value = false
  }
}

async function loadExternalHistory() {
  try {
    const res = await api.literature.getSearchHistory(10)
    const items = res.data?.items || []
    const mapped = items.map((it: any) => ({
      id: Number(it.id),
      query: String(it.query || ''),
      sources: Array.isArray(it.sources) ? it.sources : [],
      filters: it.filters || {},
    }))
    const pinned = new Set(pinnedHistory.value)
    externalHistory.value = mapped.sort((a, b) => {
      const pa = pinned.has(a.query) ? 1 : 0
      const pb = pinned.has(b.query) ? 1 : 0
      return pb - pa
    })
  } catch {
    externalHistory.value = []
  }
}

async function applyHistoryAndSearch(h: { query: string; sources: string[]; filters: any }) {
  externalQuery.value = h.query || ''
  if (Array.isArray(h.sources) && h.sources.length) {
    externalSources.value = h.sources.filter((s) => s === 'pubmed' || s === 'crossref') as Array<'pubmed' | 'crossref'>
  }
  await doExternalSearchForArticle()
}

async function deleteHistoryItem(id: number) {
  if (!id) return
  try {
    await api.literature.deleteSearchHistory(id)
    externalHistory.value = externalHistory.value.filter((h) => h.id !== id)
  } catch {
    /* ignore */
  }
}

function restorePinnedHistory() {
  try {
    const raw = localStorage.getItem(PINNED_HISTORY_KEY)
    const arr = raw ? JSON.parse(raw) : []
    pinnedHistory.value = Array.isArray(arr) ? arr.map((x) => String(x)) : []
  } catch {
    pinnedHistory.value = []
  }
}

function persistPinnedHistory() {
  localStorage.setItem(PINNED_HISTORY_KEY, JSON.stringify(pinnedHistory.value))
}

function persistPinnedAlias() {
  localStorage.setItem(PINNED_HISTORY_ALIAS_KEY, JSON.stringify(pinnedHistoryAlias.value))
}

function persistPinnedGroup() {
  localStorage.setItem(PINNED_HISTORY_GROUP_KEY, JSON.stringify(pinnedHistoryGroup.value))
}

function refreshBackupFlag() {
  hasPinnedBackup.value = pinnedBackups.value.length > 0 || Boolean(localStorage.getItem(PINNED_HISTORY_BACKUP_KEY))
}

function isHistoryPinned(query: string) {
  return pinnedHistory.value.includes(query)
}

function historyDisplayName(query: string) {
  return pinnedHistoryAlias.value[query] || query
}

function togglePinHistory(query: string) {
  const q = String(query || '').trim()
  if (!q) return
  if (isHistoryPinned(q)) {
    pinnedHistory.value = pinnedHistory.value.filter((x) => x !== q)
  } else {
    pinnedHistory.value = [q, ...pinnedHistory.value].slice(0, 30)
  }
  persistPinnedHistory()
  loadExternalHistory()
}

function restorePinnedAlias() {
  try {
    const raw = localStorage.getItem(PINNED_HISTORY_ALIAS_KEY)
    const obj = raw ? JSON.parse(raw) : {}
    pinnedHistoryAlias.value = obj && typeof obj === 'object' ? obj : {}
  } catch {
    pinnedHistoryAlias.value = {}
  }
}

function restorePinnedGroup() {
  try {
    const raw = localStorage.getItem(PINNED_HISTORY_GROUP_KEY)
    const obj = raw ? JSON.parse(raw) : {}
    pinnedHistoryGroup.value = obj && typeof obj === 'object' ? obj : {}
  } catch {
    pinnedHistoryGroup.value = {}
  }
}

async function renamePinnedHistory(query: string) {
  const q = String(query || '').trim()
  if (!q) return
  const { ElMessageBox } = await import('element-plus')
  try {
    const ret = await ElMessageBox.prompt('请输入显示名称（不改变实际检索词）', '重命名置顶检索词', {
      inputValue: pinnedHistoryAlias.value[q] || q,
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：糖尿病指南检索',
    })
    const v = String(ret.value || '').trim()
    if (!v) {
      delete pinnedHistoryAlias.value[q]
    } else {
      pinnedHistoryAlias.value[q] = v
    }
    persistPinnedAlias()
  } catch {
    // cancelled
  }
}

async function setPinnedGroup(query: string) {
  const q = String(query || '').trim()
  if (!q) return
  const { ElMessageBox } = await import('element-plus')
  try {
    const ret = await ElMessageBox.prompt('请输入分组名称（可留空清除分组）', '设置分组', {
      inputValue: pinnedHistoryGroup.value[q] || '',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：代谢/肿瘤/心血管',
    })
    const v = String(ret.value || '').trim()
    if (!v) delete pinnedHistoryGroup.value[q]
    else pinnedHistoryGroup.value[q] = v
    persistPinnedGroup()
  } catch {
    // cancelled
  }
}

function onHistoryDragStart(query: string) {
  if (!isHistoryPinned(query)) return
  historyDragFrom.value = query
}

function onHistoryDragOver(_query: string) {
  // keep drop zone active
}

function onHistoryDrop(targetQuery: string) {
  const from = historyDragFrom.value
  const to = targetQuery
  historyDragFrom.value = ''
  if (!from || !to || from === to) return
  const list = [...pinnedHistory.value]
  const fromIdx = list.indexOf(from)
  const toIdx = list.indexOf(to)
  if (fromIdx < 0 || toIdx < 0) return
  const [moved] = list.splice(fromIdx, 1)
  list.splice(toIdx, 0, moved)
  pinnedHistory.value = list
  persistPinnedHistory()
  loadExternalHistory()
}

function _stableObj(input: Record<string, string>) {
  const out: Record<string, string> = {}
  for (const k of Object.keys(input || {}).sort()) out[k] = String(input[k] || '')
  return out
}

function _payloadForChecksum(payload: any) {
  return JSON.stringify({
    version: Number(payload?.version || PINNED_CONFIG_VERSION),
    pinned: Array.isArray(payload?.pinned) ? payload.pinned.map((x: any) => String(x)) : [],
    alias: _stableObj(payload?.alias || {}),
    group: _stableObj(payload?.group || {}),
  })
}

function _simpleChecksum(payload: any) {
  const s = _payloadForChecksum(payload)
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h += (h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24)
  }
  return (h >>> 0).toString(16).padStart(8, '0')
}

async function exportPinnedConfig() {
  const payload = {
    version: PINNED_CONFIG_VERSION,
    exported_at: new Date().toISOString(),
    pinned: pinnedHistory.value,
    alias: pinnedHistoryAlias.value,
    group: pinnedHistoryGroup.value,
  }
  const checksum = _simpleChecksum(payload)
  const full = { ...payload, checksum }
  const text = JSON.stringify(full, null, 2)
  const blob = new Blob([text], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'medcomm-pinned-search-config.json'
  a.click()
  URL.revokeObjectURL(url)
}

function makePinnedSnapshot() {
  return {
    version: PINNED_CONFIG_VERSION,
    saved_at: new Date().toISOString(),
    pinned: [...pinnedHistory.value],
    alias: { ...pinnedHistoryAlias.value },
    group: { ...pinnedHistoryGroup.value },
  }
}

function savePinnedBackup() {
  const snap = makePinnedSnapshot()
  localStorage.setItem(PINNED_HISTORY_BACKUP_KEY, JSON.stringify(snap))
  const arr = [...pinnedBackups.value]
  arr.unshift({ id: String(Date.now()), saved_at: snap.saved_at, pinned: snap.pinned, alias: snap.alias, group: snap.group })
  pinnedBackups.value = arr.slice(0, 10)
  localStorage.setItem(PINNED_HISTORY_BACKUPS_KEY, JSON.stringify(pinnedBackups.value))
  refreshBackupFlag()
}

async function rollbackPinnedBackup() {
  if (!pinnedBackups.value.length) return
  selectedRollbackId.value = pinnedBackups.value[0]?.id || ''
  showRollbackDialog.value = true
}

async function confirmRollbackBySelection() {
  const { ElMessage } = await import('element-plus')
  const candidate = pinnedBackups.value.find((b) => b.id === selectedRollbackId.value)
  if (!candidate) return
  try {
    const pinned = Array.isArray(candidate.pinned) ? candidate.pinned.map((x: any) => String(x)) : []
    const alias = candidate.alias && typeof candidate.alias === 'object' ? candidate.alias : {}
    const group = candidate.group && typeof candidate.group === 'object' ? candidate.group : {}
    pinnedHistory.value = pinned.slice(0, 100)
    pinnedHistoryAlias.value = alias
    pinnedHistoryGroup.value = group
    persistPinnedHistory()
    persistPinnedAlias()
    persistPinnedGroup()
    await loadExternalHistory()
    showRollbackDialog.value = false
    ElMessage.success('已回滚到所选备份')
  } catch {
    ElMessage.error('备份数据无效，无法回滚')
  }
}

function _persistPinnedBackups() {
  localStorage.setItem(PINNED_HISTORY_BACKUPS_KEY, JSON.stringify(pinnedBackups.value))
  refreshBackupFlag()
}

function deletePinnedBackup(id: string) {
  const target = String(id || '')
  if (!target) return
  pinnedBackups.value = pinnedBackups.value.filter((b) => b.id !== target)
  if (selectedRollbackId.value === target) {
    selectedRollbackId.value = pinnedBackups.value[0]?.id || ''
  }
  _persistPinnedBackups()
}

function clearAllPinnedBackups() {
  pinnedBackups.value = []
  selectedRollbackId.value = ''
  localStorage.removeItem(PINNED_HISTORY_BACKUPS_KEY)
  localStorage.removeItem(PINNED_HISTORY_BACKUP_KEY)
  refreshBackupFlag()
}

async function importPinnedConfig() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'application/json,.json'
  input.onchange = async () => {
    const f = input.files?.[0]
    if (!f) return
    const { ElMessage, ElMessageBox } = await import('element-plus')
    try {
      const txt = await f.text()
      const obj = JSON.parse(txt || '{}')
      const version = Number(obj?.version || 0)
      if (version !== PINNED_CONFIG_VERSION) {
        ElMessage.error(`配置版本不兼容（当前仅支持 v${PINNED_CONFIG_VERSION}）`)
        return
      }
      const importedChecksum = String(obj?.checksum || '')
      const computedChecksum = _simpleChecksum(obj)
      if (!importedChecksum || importedChecksum !== computedChecksum) {
        ElMessage.error('配置文件校验失败，可能已损坏或被修改')
        return
      }
      const pinned = Array.isArray(obj?.pinned) ? obj.pinned.map((x: any) => String(x)) : []
      const alias = obj?.alias && typeof obj.alias === 'object' ? obj.alias : {}
      const group = obj?.group && typeof obj.group === 'object' ? obj.group : {}
      pendingImportConfig.value = { pinned, alias, group }
      importDimensions.value = ['pinned', 'alias', 'group']
      showImportOptionsDialog.value = true
      return

      const incomingSet = new Set(pinned)
      const currentSet = new Set(pinnedHistory.value)
      const toAdd = importPinned ? [...incomingSet].filter((x) => !currentSet.has(x)).length : 0
      const toKeep = importPinned ? [...incomingSet].filter((x) => currentSet.has(x)).length : 0
      const toReplaceAlias = importAlias ? Object.keys(alias).filter((k) => pinnedHistoryAlias.value[k] && pinnedHistoryAlias.value[k] !== alias[k]).length : 0
      const toReplaceGroup = importGroup ? Object.keys(group).filter((k) => pinnedHistoryGroup.value[k] && pinnedHistoryGroup.value[k] !== group[k]).length : 0
      await ElMessageBox.alert(
        `导入预览：\n- 新增置顶词：${toAdd}\n- 与现有重叠：${toKeep}\n- 将覆盖别名：${toReplaceAlias}\n- 将覆盖分组：${toReplaceGroup}`,
        '导入差异预览',
        { confirmButtonText: '继续' }
      )

      let mode: 'overwrite' | 'merge' = 'merge'
      try {
        await ElMessageBox.confirm(
          '选择导入方式：确定=覆盖现有配置，取消=与现有配置合并',
          '导入置顶配置',
          {
            confirmButtonText: '覆盖',
            cancelButtonText: '合并',
            distinguishCancelAndClose: true,
            type: 'warning',
          }
        )
        mode = 'overwrite'
      } catch (e: any) {
        if (e === 'cancel') mode = 'merge'
        else return
      }

      // 覆盖或合并前，自动备份
      savePinnedBackup()

      if (mode === 'overwrite') {
        if (importPinned) pinnedHistory.value = pinned.slice(0, 100)
        if (importAlias) pinnedHistoryAlias.value = alias
        if (importGroup) pinnedHistoryGroup.value = group
      } else {
        if (importPinned) {
          const mergedPinned = [...new Set([...pinnedHistory.value, ...pinned])].slice(0, 100)
          pinnedHistory.value = mergedPinned
        }
        if (importAlias) pinnedHistoryAlias.value = { ...pinnedHistoryAlias.value, ...alias }
        if (importGroup) pinnedHistoryGroup.value = { ...pinnedHistoryGroup.value, ...group }
      }
      persistPinnedHistory()
      persistPinnedAlias()
      persistPinnedGroup()
      await loadExternalHistory()
      ElMessage.success('置顶配置导入成功')
    } catch {
      ElMessage.error('配置文件格式无效')
    }
  }
  input.click()
}

async function confirmImportWithDimensions() {
  const { ElMessage, ElMessageBox } = await import('element-plus')
  const cfg = pendingImportConfig.value
  if (!cfg) return
  const importPinned = importDimensions.value.includes('pinned')
  const importAlias = importDimensions.value.includes('alias')
  const importGroup = importDimensions.value.includes('group')
  if (!importPinned && !importAlias && !importGroup) {
    ElMessage.warning('未选择任何导入维度')
    return
  }
  const pinned = cfg.pinned || []
  const alias = cfg.alias || {}
  const group = cfg.group || {}
  const incomingSet = new Set(pinned)
  const currentSet = new Set(pinnedHistory.value)
  const toAdd = importPinned ? [...incomingSet].filter((x) => !currentSet.has(x)).length : 0
  const toKeep = importPinned ? [...incomingSet].filter((x) => currentSet.has(x)).length : 0
  const toReplaceAlias = importAlias ? Object.keys(alias).filter((k) => pinnedHistoryAlias.value[k] && pinnedHistoryAlias.value[k] !== alias[k]).length : 0
  const toReplaceGroup = importGroup ? Object.keys(group).filter((k) => pinnedHistoryGroup.value[k] && pinnedHistoryGroup.value[k] !== group[k]).length : 0
  await ElMessageBox.alert(
    `导入预览：\n- 新增置顶词：${toAdd}\n- 与现有重叠：${toKeep}\n- 将覆盖别名：${toReplaceAlias}\n- 将覆盖分组：${toReplaceGroup}`,
    '导入差异预览',
    { confirmButtonText: '继续' }
  )

  let mode: 'overwrite' | 'merge' = 'merge'
  try {
    await ElMessageBox.confirm(
      '选择导入方式：确定=覆盖现有配置，取消=与现有配置合并',
      '导入置顶配置',
      {
        confirmButtonText: '覆盖',
        cancelButtonText: '合并',
        distinguishCancelAndClose: true,
        type: 'warning',
      }
    )
    mode = 'overwrite'
  } catch (e: any) {
    if (e === 'cancel') mode = 'merge'
    else return
  }

  savePinnedBackup()
  if (mode === 'overwrite') {
    if (importPinned) pinnedHistory.value = pinned.slice(0, 100)
    if (importAlias) pinnedHistoryAlias.value = alias
    if (importGroup) pinnedHistoryGroup.value = group
  } else {
    if (importPinned) pinnedHistory.value = [...new Set([...pinnedHistory.value, ...pinned])].slice(0, 100)
    if (importAlias) pinnedHistoryAlias.value = { ...pinnedHistoryAlias.value, ...alias }
    if (importGroup) pinnedHistoryGroup.value = { ...pinnedHistoryGroup.value, ...group }
  }
  persistPinnedHistory()
  persistPinnedAlias()
  persistPinnedGroup()
  showImportOptionsDialog.value = false
  pendingImportConfig.value = null
  await loadExternalHistory()
  ElMessage.success('置顶配置导入成功')
}

function _toSearchSaveItem(r: any) {
  return {
    source: r.source,
    source_id: r.source_id || '',
    title: r.title || '',
    authors: (r.authors || []).map((a: any) => ({ name: a.name || '', affil: a.affil || '' })),
    journal: r.journal || '',
    year: r.year || null,
    volume: r.volume || '',
    issue: r.issue || '',
    pages: r.pages || '',
    doi: r.doi || null,
    pmid: r.pmid || null,
    url: r.url || '',
    abstract: r.abstract || '',
    pub_types: r.pub_types || [],
    cite_count: r.cite_count || 0,
    open_access_url: r.open_access_url || '',
  }
}

async function saveAndBindExternalSelected() {
  if (!articleId.value || !externalSelectedRows.value.length) return
  externalBinding.value = true
  try {
    const paperIds: number[] = []
    for (const row of externalSelectedRows.value) {
      if (row.local_status === 'saved' && row.local_id) {
        paperIds.push(Number(row.local_id))
        continue
      }
      const saveRes = await api.literature.saveSearchResults({ items: [_toSearchSaveItem(row)] })
      const detail = (saveRes.data?.details || [])[0] || {}
      if (detail.status === 'created' && detail.paper_id) {
        paperIds.push(Number(detail.paper_id))
      } else if (detail.status === 'duplicate' && detail.existing_id) {
        paperIds.push(Number(detail.existing_id))
      }
    }
    const uniqIds = [...new Set(paperIds)].filter((x) => Number.isFinite(x) && x > 0)
    if (!uniqIds.length) return
    const sectionId = bindingScope.value === 'section' ? currentSectionId.value ?? undefined : undefined
    await api.literature.bindPapers(articleId.value, { paper_ids: uniqIds, section_id: sectionId })
    const { ElMessage } = await import('element-plus')
    ElMessage.success(`已绑定 ${uniqIds.length} 篇文献`)
    await loadBindings()
    await doExternalSearchForArticle()
  } catch (e: any) {
    const { ElMessage } = await import('element-plus')
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  } finally {
    externalBinding.value = false
  }
}

async function bindExternalSelectedNoSave() {
  if (!articleId.value || !externalSelectedRows.value.length) return
  externalBinding.value = true
  try {
    const items = externalSelectedRows.value.map((r: any) => ({
      source: r.source,
      source_id: r.source_id || '',
      doi: r.doi || null,
      pmid: r.pmid || null,
      title: r.title || '',
      authors: (r.authors || []).map((a: any) => ({ name: a.name || '', affil: a.affil || '' })),
      journal: r.journal || '',
      year: r.year || null,
      url: r.url || '',
      abstract: r.abstract || '',
    }))
    const sectionId = bindingScope.value === 'section' ? currentSectionId.value ?? undefined : undefined
    await api.literature.bindExternalRefs(articleId.value, { items, section_id: sectionId })
    const { ElMessage } = await import('element-plus')
    ElMessage.success(`已绑定 ${items.length} 条外部引用`)
    await loadBindings()
  } catch (e: any) {
    const { ElMessage } = await import('element-plus')
    ElMessage.error(e?.response?.data?.detail || '绑定失败')
  } finally {
    externalBinding.value = false
  }
}

async function onApiKeyCommand(cmd: string) {
  const { ElMessageBox, ElMessage } = await import('element-plus')
  if (cmd === 'applyNcbi') {
    window.open('https://www.ncbi.nlm.nih.gov/account/', '_blank')
    return
  }
  if (cmd === 'applyS2') {
    window.open('https://www.semanticscholar.org/product/api', '_blank')
    return
  }
  if (cmd === 'configNcbi') {
    try {
      const current = await api.system.getNcbiKey()
      const masked = current.data?.masked || ''
      const { value } = await ElMessageBox.prompt(
        `请输入 NCBI API Key（当前：${masked || '未配置'}）\n申请地址：https://www.ncbi.nlm.nih.gov/account/`,
        '配置 NCBI Key（PubMed 速率提升）',
        {
          confirmButtonText: '保存',
          cancelButtonText: '取消',
          inputType: 'password',
          inputPlaceholder: '例如：xxxxxxxxxxxxxxxx（16位字母数字）',
        }
      )
      await api.system.setNcbiKey(String(value || '').trim())
      ElMessage.success('已保存 NCBI Key（仅当前用户）')
    } catch (e: any) {
      if (e === 'cancel' || e === 'close') return
      ElMessage.error('保存失败')
    }
  }
  if (cmd === 'configS2') {
    try {
      const current = await api.system.getS2Key()
      const masked = current.data?.masked || ''
      const { value } = await ElMessageBox.prompt(
        `请输入 Semantic Scholar API Key（当前：${masked || '未配置'}）\n申请地址：https://www.semanticscholar.org/product/api`,
        '配置 Semantic Scholar Key（提升速率限制）',
        {
          confirmButtonText: '保存',
          cancelButtonText: '取消',
          inputType: 'password',
          inputPlaceholder: '例如：xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx（40位）',
        }
      )
      await api.system.setS2Key(String(value || '').trim())
      ElMessage.success('已保存 Semantic Scholar Key（仅当前用户）')
    } catch (e: any) {
      if (e === 'cancel' || e === 'close') return
      ElMessage.error('保存失败')
    }
  }
}

async function confirmBind() {
  if (!articleId.value || !selectedPaperIds.value.length) return
  if (bindingScope.value === 'section' && !currentSectionId.value) return
  try {
    const sectionId = bindingScope.value === 'section' ? currentSectionId.value! : undefined
    await api.literature.bindPapers(articleId.value, { paper_ids: selectedPaperIds.value, section_id: sectionId })
    const { ElMessage } = await import('element-plus')
    ElMessage.success('已添加')
    showBindDialog.value = false
    selectedPaperIds.value = []
    await loadBindings()
  } catch (e: any) {
    const { ElMessage } = await import('element-plus')
    ElMessage.error(e?.response?.data?.detail || '添加失败')
  }
}

async function removeBinding(bindingId: number) {
  if (!articleId.value) return
  try {
    await api.literature.deleteBinding(articleId.value, bindingId)
    await loadBindings()
  } catch {
    const { ElMessage } = await import('element-plus')
    ElMessage.error('移除失败')
  }
}

async function removeExternalRef(refId: number) {
  if (!articleId.value || !refId) return
  try {
    await api.literature.deleteExternalRef(articleId.value, refId)
    await loadBindings()
  } catch {
    const { ElMessage } = await import('element-plus')
    ElMessage.error('移除失败')
  }
}

function syncCitationRefsInEditor() {
  if (!editorRef.value?.normalizeCitationRefs) return
  nextTick(() => {
    editorRef.value?.normalizeCitationRefs?.(citationIndexMap.value)
  })
}

function openPaperDetail(paperId: number) {
  if (!paperId) return
  router.push({ name: 'literature-paper', params: { paperId } })
}

function showExternalRefDetail(b: any) {
  activeExternalRef.value = b
  showExternalRefDialog.value = true
  // 统一摘要按需拉取：优先 PMID，其次 DOI
  if (!b?.abstract && (b?.pmid || b?.doi)) {
    const params = b?.pmid ? { pmid: String(b.pmid) } : { doi: String(b.doi) }
    api.literature.fetchSearchAbstract(params)
      .then((res: any) => {
        const abs = res?.data?.abstract || ''
        if (!abs || !activeExternalRef.value) return
        const samePmid = params && 'pmid' in params
          ? String(activeExternalRef.value.pmid || '') === String((params as any).pmid || '')
          : true
        const sameDoi = params && 'doi' in params
          ? String((activeExternalRef.value.doi || '')).toLowerCase() === String((params as any).doi || '').toLowerCase()
          : true
        if (samePmid && sameDoi) {
          activeExternalRef.value = { ...activeExternalRef.value, abstract: abs }
        }
      })
      .catch(() => {})
  }
}

function openExternalUrl(url: string) {
  if (!url) return
  window.open(url, '_blank')
}

async function insertCitation(binding: any) {
  if (!binding?.refIndex) return
  const ok = editorRef.value?.insertCitationRef?.({
    paperId: binding._kind === 'local' ? binding.paper_id : undefined,
    externalRefId: binding._kind === 'external' ? binding.ref_id : undefined,
    articleId: articleId.value,
    sectionId: currentSectionId.value ?? undefined,
    index: binding.refIndex,
    title: binding.title || `参考文献[${binding.refIndex}]`,
  })
  if (!ok) {
    const { ElMessage } = await import('element-plus')
    ElMessage.warning('请先点击正文，再插入引用')
  }
}

function onCitationClick(payload: { paperId: number; externalRefId?: number }) {
  if (payload?.paperId) {
    openPaperDetail(payload.paperId)
    return
  }
  if (payload?.externalRefId) {
    const hit = indexedBindings.value.find((b: any) => b._kind === 'external' && Number(b.ref_id) === Number(payload.externalRefId))
    if (hit) showExternalRefDetail(hit)
  }
}

function onMedClaimClick(payload: {
  paperId: number
  evidenceSnippet: string
  evidenceSource: string
  chunkId: string
  text: string
}) {
  claimEvidencePayload.value = payload
  claimEvidenceVisible.value = true
}

function openPaperFromClaimEvidence() {
  const id = claimEvidencePayload.value?.paperId
  if (id) openPaperDetail(id)
  claimEvidenceVisible.value = false
}

async function handleGenerate() {
  if (!currentSectionId.value) return
  articleStore.setOllamaWarning(null)
  articleStore.setVerificationReport(null)
  await generateSection(currentSectionId.value, {
    onDone: async () => {
      await loadArticle(currentSectionId.value ?? undefined)
      streamedText.value = ''
    },
    onVerifyReport: (r) => articleStore.setVerificationReport(r),
    onOllamaWarning: (msg) => articleStore.setOllamaWarning(msg),
  })
}

async function handleExport(format: string) {
  if (!articleId.value) return
  try {
    const checkRes = await api.medcomm.exportCheck(articleId.value)
    const check = checkRes.data
    if (!check?.can_export) {
      exportCheckMessage.value = check?.message || '发现可优化内容，建议先修订再导出。'
      exportDataWarnings.value = Array.isArray(check?.data_warnings) ? check.data_warnings : []
      exportAbsoluteTerms.value = Array.isArray(check?.absolute_terms) ? check.absolute_terms : []
      exportOrphanCitations.value = Array.isArray(check?.orphan_citations) ? check.orphan_citations : []
      exportValidPaperIds.value = Array.isArray(check?.valid_paper_ids) ? check.valid_paper_ids : []
      pendingExportFormat.value = format
      exportCheckDialogVisible.value = true
      return
    }
    await doExport(format)
  } catch (e) {
    console.error('导出失败', e)
    const msg = await axiosErrorDetail(e)
    const { ElMessage } = await import('element-plus')
    ElMessage.error(msg)
  }
}

function bumpLocate(needle: string) {
  locateToken.value += 1
  locateRequest.value = { text: needle, token: locateToken.value }
}

function scrollEditorAreaIntoView() {
  nextTick(() => {
    document.querySelector('.editor-area')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}

async function onEditorLocateResult(ok: boolean) {
  if (!awaitLocateFeedback.value) return
  awaitLocateFeedback.value = false
  if (!ok) {
    const { ElMessage } = await import('element-plus')
    ElMessage.warning('未在编辑器中定位到该文本，请手动查找或确认是否位于图片等特殊块中')
  }
}

async function locateIssueText(text: string) {
  const needle = (text || '').trim()
  if (!needle || !articleId.value) return

  let targetSectionId: number | null = null
  const curId = currentSectionId.value
  if (contentJson.value && extractPlainFromTiptapJson(contentJson.value).includes(needle)) {
    targetSectionId = curId
  } else {
    const sections = article.value?.sections || []
    for (const s of sections) {
      if (s.id === curId) continue
      try {
        const res = await api.medcomm.getArticle(articleId.value, s.id)
        const j = res.data?.content_json
        if (j && extractPlainFromTiptapJson(j).includes(needle)) {
          targetSectionId = s.id
          break
        }
      } catch {
        /* 忽略单章拉取失败 */
      }
    }
  }

  if (targetSectionId == null) {
    const { ElMessage } = await import('element-plus')
    ElMessage.warning('未在任何章节正文中找到该片段（导出检查为全文合并结果）')
    return
  }

  if (targetSectionId !== curId) {
    currentSectionId.value = targetSectionId
    await loadArticle(targetSectionId)
    await nextTick()
    await nextTick()
  }

  awaitLocateFeedback.value = true
  bumpLocate(needle)
  scrollEditorAreaIntoView()
}

async function locateOrphanCitation(item: { section_id: number; section_title: string; text: string }) {
  if (!item?.section_id || !item?.text?.trim()) return
  if (currentSectionId.value !== item.section_id) {
    currentSectionId.value = item.section_id
    await loadArticle(item.section_id)
    await nextTick()
    await nextTick()
  }
  awaitLocateFeedback.value = true
  bumpLocate(item.text.trim())
  scrollEditorAreaIntoView()
}

async function removeOrphanCitations() {
  if (!articleId.value || !exportOrphanCitations.value.length) return
  const validSet = new Set(exportValidPaperIds.value || [])
  if (!validSet.size) return
  const sectionIds = [...new Set(exportOrphanCitations.value.map((o) => o.section_id))]
  const { ElMessage } = await import('element-plus')
  try {
    for (const sid of sectionIds) {
      const res = await api.medcomm.getArticle(articleId.value, sid)
      const json = res.data?.content_json
      if (!json) continue
      const cleaned = stripOrphanCitationMarks(json, validSet)
      await api.medcomm.updateArticleContent(articleId.value, cleaned, sid)
    }
    ElMessage.success('已移除孤儿引用')
    exportOrphanCitations.value = []
    if (sectionIds.includes(currentSectionId.value!)) {
      await loadArticle(currentSectionId.value ?? undefined)
    }
    exportCheckDialogVisible.value = false
    pendingExportFormat.value = null
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '移除失败')
  }
}

async function confirmExportWithWarnings() {
  if (!pendingExportFormat.value) {
    exportCheckDialogVisible.value = false
    return
  }
  const fmt = pendingExportFormat.value
  exportCheckDialogVisible.value = false
  await doExport(fmt)
}

async function saveArticleTitle() {
  if (!articleId.value) return
  const next = articleTitleDraft.value.trim()
  const prev = (article.value?.title || '').trim()
  if (next === prev) return
  try {
    const res = await api.medcomm.patchArticleTitle(articleId.value, next)
    if (res.data) {
      article.value = { ...article.value, ...res.data }
      articleStore.setCurrent(article.value)
    }
  } catch (e: unknown) {
    ElMessage.error(axiosErrorDetail(e as any) || '保存标题失败')
    articleTitleDraft.value = prev
  }
}

async function handleGenerateTitle() {
  if (!articleId.value) return
  titleGenerating.value = true
  try {
    const res = await api.medcomm.generateArticleTitle(articleId.value)
    const t = (res.data?.title || '').trim()
    if (t) {
      articleTitleDraft.value = t
      article.value = { ...article.value, ...res.data }
      articleStore.setCurrent(article.value)
      ElMessage.success('已根据全文总结标题')
    }
  } catch (e: unknown) {
    ElMessage.error(axiosErrorDetail(e as any) || '生成标题失败')
  } finally {
    titleGenerating.value = false
  }
}

async function copyMarkdownExport() {
  if (!articleId.value) return
  copyMdLoading.value = true
  try {
    const res = await api.medcomm.exportArticle(articleId.value, 'md')
    const blob = res.data as Blob
    const text = await blob.text()
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制 Markdown（含参考文献与配图说明）')
  } catch (e: unknown) {
    ElMessage.error(axiosErrorDetail(e as any) || '复制失败')
  } finally {
    copyMdLoading.value = false
  }
}

async function doExport(format: string) {
  const res = await api.medcomm.exportArticle(articleId.value, format)
  const blob = new Blob([res.data])
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const ext = { html: 'html', docx: 'docx', pdf: 'pdf', txt: 'txt', md: 'md' }[format] || 'txt'
  a.download = `${article.value?.topic || 'article'}.${ext}`
  a.click()
  URL.revokeObjectURL(url)
}

let saveTimer: ReturnType<typeof setTimeout> | null = null

function onContentUpdate(json: any) {
  contentJson.value = json
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    if (!articleId.value) return
    try {
      await api.medcomm.updateArticleContent(articleId.value, json, currentSectionId.value ?? undefined)
    } catch (e) {
      console.error('保存失败', e)
    } finally {
      saveTimer = null
    }
  }, 800)
}

onMounted(() => {
  restorePinnedHistory()
  restorePinnedAlias()
  restorePinnedGroup()
  try {
    const raw = localStorage.getItem(PINNED_HISTORY_BACKUPS_KEY)
    const arr = raw ? JSON.parse(raw) : []
    pinnedBackups.value = Array.isArray(arr) ? arr : []
  } catch {
    pinnedBackups.value = []
  }
  refreshBackupFlag()
  const querySectionId = getSectionIdFromQuery()
  if (querySectionId) currentSectionId.value = querySectionId
  externalQuery.value = String(article.value?.topic || article.value?.title || '')
  loadArticle(querySectionId ?? undefined)
  loadBindings()
  syncCitationRefsInEditor()
  window.addEventListener(AUTH_USER_CHANGED_EVENT, handleAuthUserChanged as EventListener)
})
onUnmounted(() => {
  window.removeEventListener(AUTH_USER_CHANGED_EVENT, handleAuthUserChanged as EventListener)
  articleStore.clear()
})
watch(articleId, () => {
  loadArticle()
  loadBindings()
})
watch(bindingScope, () => loadBindings())
watch(
  () => articleStore.editorLocatePayload?.nonce,
  () => {
    const p = articleStore.editorLocatePayload
    if (p?.text) void locateIssueText(p.text)
  },
)
watch(showBindDialog, (v) => { if (v) searchPapersForBind() })
watch(showExternalSearchDialog, (v) => {
  if (!v) return
  if (!externalQuery.value) externalQuery.value = String(article.value?.topic || article.value?.title || '')
  loadExternalHistory()
  doExternalSearchForArticle()
})
watch(indexedBindings, () => {
  syncCitationRefsInEditor()
}, { deep: true })
watch(
  () => route.query.section_id,
  () => {
    const qid = getSectionIdFromQuery()
    if (!qid || qid === currentSectionId.value) return
    currentSectionId.value = qid
    loadArticle(qid)
    loadBindings()
  }
)

async function handleAuthUserChanged() {
  await loadBindings()
  if (showExternalSearchDialog.value) {
    await loadExternalHistory()
    if (externalQuery.value.trim()) await doExternalSearchForArticle()
  }
}
</script>

<style scoped>
.translate-assist-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 8px 12px;
  margin-bottom: 10px;
  background: #f0f5ff;
  border: 1px solid #d6e4ff;
  border-radius: 6px;
  font-size: 13px;
}
.translate-assist-label {
  font-weight: 600;
  color: var(--el-color-primary);
  white-space: nowrap;
}
.translate-assist-result {
  padding: 2px 10px;
  background: #fff;
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 4px;
  color: var(--el-color-primary);
  font-weight: 500;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.translate-assist-tip {
  margin-left: auto;
  color: #909399;
  font-size: 12px;
  white-space: nowrap;
}
.bindings-panel {
  margin: 0 1rem 0.5rem;
}
.bindings-panel :deep(.el-collapse-item__header) { padding-left: 0; }
.bindings-content { padding: 0.25rem 0; }
.bindings-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}
.bindings-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.bindings-empty {
  color: #9ca3af;
  font-size: 0.85rem;
  padding: 0.5rem 0;
}
.version-snap-panel {
  padding: 0.25rem 0;
}
.vs-hint {
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
  margin: 0 0 0.75rem;
}
.vs-block {
  margin-bottom: 1rem;
}
.vs-label {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 0.35rem;
}
.vs-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}
.bindings-list {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0;
}
.binding-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.25rem 0;
  font-size: 0.9em;
}
.binding-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: 0.5rem; }
.binding-actions { display: inline-flex; align-items: center; gap: 2px; flex-shrink: 0; }
.external-search-filters {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 0.5rem 0;
}
.source-stats-row { display: flex; gap: 8px; margin: 6px 0 8px; }
.source-stat-card { border: 1px solid var(--el-border-color); border-radius: 6px; padding: 6px 8px; min-width: 140px; background: #fff; }
.source-stat-title { font-weight: 600; margin-bottom: 4px; }
.source-stat-line { font-size: 12px; color: var(--el-text-color-secondary); }
.source-stat-ok { font-size: 12px; color: var(--el-color-success); margin-top: 2px; }
.source-stat-error { font-size: 12px; color: var(--el-color-danger); margin-top: 2px; }
.external-history {
  margin: 0.35rem 0 0.65rem;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.external-history-title { color: #6b7280; font-size: 0.85rem; }
.external-history-item { cursor: pointer; }
.external-history-chip { display: inline-flex; align-items: center; gap: 2px; }
.external-history-chip[draggable="true"] { cursor: move; }
.external-history-rename { padding: 0 2px; min-height: 20px; }
.external-history-group { padding: 0 2px; min-height: 20px; }
.external-history-pin { padding: 0 2px; min-height: 20px; }
.external-history-del { padding: 0 2px; min-height: 20px; }
.external-group-tabs { margin: 0 0 0.4rem; }
.rollback-list { display: flex; flex-direction: column; gap: 0.4rem; width: 100%; }
.rollback-item { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; }
.article-editor {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.editor-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #eee;
  background: #fff;
}
.article-title { font-size: 1rem; margin: 0 0 0.5rem 0; }
.title-edit-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.35rem;
}
.article-title-input {
  flex: 1 1 220px;
  min-width: 0;
  max-width: 560px;
}
.topic-hint {
  margin: 0 0 0.5rem;
  font-size: 0.8rem;
  color: #6b7280;
}
.tags { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; }
.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid #eee;
  background: #fafafa;
}

.verify-empty-hint {
  margin: 0;
  font-size: 0.85rem;
  color: #6b7280;
  line-height: 1.5;
}

.claim-evidence-body {
  font-size: 0.875rem;
  line-height: 1.5;
}
.claim-evidence-body .ce-row {
  margin: 0 0 0.5rem;
}
.claim-evidence-body .ce-label {
  display: inline-block;
  min-width: 3em;
  color: #6b7280;
  margin-right: 0.35rem;
}
.claim-evidence-body .ce-snippet {
  margin-top: 0.5rem;
  padding: 0.65rem 0.75rem;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  white-space: pre-wrap;
  max-height: 220px;
  overflow-y: auto;
}

.section-tabs {
  padding: 0.5rem 1rem;
  border-bottom: 1px solid #eee;
  background: #fafafa;
}

.section-tabs :deep(.el-radio-group) {
  display: flex;
  flex-wrap: wrap;
}

.stream-preview {
  padding: 0.5rem 1rem;
  background: #f0f9ff;
  border-bottom: 1px solid #e0f2fe;
  font-size: 0.9rem;
  white-space: pre-wrap;
  max-height: 120px;
  overflow-y: auto;
}

.series-visual-collapse {
  margin: 0 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fafafa;
}

.series-visual-hint {
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
  color: #6b7280;
  line-height: 1.5;
}

.series-seed-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin: 0.75rem 0;
  flex-wrap: wrap;
}

.series-seed-label {
  font-size: 0.875rem;
  color: #374151;
}

.editor-area {
  flex: 1;
  overflow: auto;
  padding: 1rem;
}

.export-check-summary {
  margin-bottom: 0.75rem;
  color: #374151;
}

.export-check-group {
  margin-bottom: 0.75rem;
}

.export-check-title {
  font-size: 0.875rem;
  color: #6b7280;
  margin-bottom: 0.35rem;
}

.export-check-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.35rem 0.5rem;
  border: 1px solid #f3f4f6;
  border-radius: 6px;
  margin-bottom: 0.35rem;
  gap: 0.5rem;
}

.export-check-text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 0.82rem;
  color: #111827;
  word-break: break-all;
}
</style>
