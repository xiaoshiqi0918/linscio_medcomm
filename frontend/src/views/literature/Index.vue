<template>
  <div class="literature-index">
    <h2>文献支撑库</h2>
    <div class="page-layout">
      <aside class="sidebar">
        <div class="side-block">
          <div class="side-nav-item" :class="{ active: !trashed && !activeCollectionId && !activeTagId && !readStatusFilter }" @click="resetSidebarFilters(false)">
            📚 全部文献 <span>({{ totalAll }})</span>
          </div>
          <div class="side-nav-item" :class="{ active: !trashed && readStatusFilter === 'unread' }" @click="setReadStatusFilter('unread')">
            📖 未读 <span>({{ totalUnread }})</span>
          </div>
          <div class="side-nav-item" :class="{ active: trashed }" @click="resetSidebarFilters(true)">
            🗑️ 回收站 <span>({{ totalTrash }})</span>
          </div>
        </div>

        <div class="side-block">
          <div class="side-title-row">
            <span class="side-title">集合</span>
            <el-button link type="primary" size="small" @click.stop="showCreateCollectionDialog = true" title="新建集合">+</el-button>
          </div>
          <div
            v-for="c in flatCollections"
            :key="`coll-${c.id}`"
            class="side-nav-item side-coll"
            :class="{ active: !trashed && activeCollectionId === c.id }"
            :style="{ paddingLeft: `${10 + c.depth * 14}px` }"
            @click="selectCollection(c.id)"
          >
            📁 {{ c.name }} <span>({{ c.count || 0 }})</span>
          </div>
        </div>

        <div class="side-block">
          <div class="side-title-row">
            <span class="side-title">标签</span>
            <el-button link type="primary" size="small" @click.stop="showCreateTagDialog = true" title="新建标签">+</el-button>
          </div>
          <div
            v-for="t in tags"
            :key="`tag-${t.id}`"
            class="side-nav-item"
            :class="{ active: !trashed && activeTagId === t.id }"
            @click="selectTag(t.id)"
          >
            🏷 {{ t.name }} <span>({{ t.paper_count || 0 }})</span>
          </div>
        </div>
      </aside>

      <section class="main-panel">
    <div class="toolbar">
      <el-radio-group v-model="trashed" @change="onTrashedChange" size="small">
        <el-radio-button :value="false">文献库</el-radio-button>
        <el-radio-button :value="true">回收站</el-radio-button>
      </el-radio-group>
      <el-button type="primary" @click="showAddDialog = true" :disabled="trashed">添加文献</el-button>
      <el-upload
        :auto-upload="false"
        accept=".pdf,.ris,.bib,.bibtex"
        :limit="1"
        :on-change="handleImport"
        :show-file-list="false"
        :disabled="importPolling"
      >
        <el-button :loading="importPolling">导入 (RIS/BibTeX/PDF)</el-button>
      </el-upload>
      <el-select v-model="readStatusFilter" placeholder="筛选阅读状态" clearable style="width: 140px;" @change="onFilterChanged">
        <el-option label="未读" value="unread" />
        <el-option label="在读" value="reading" />
        <el-option label="已读" value="read" />
      </el-select>
      <el-select v-model="sortBy" style="width: 140px;" @change="onFilterChanged">
        <el-option label="添加时间" value="created_at" />
        <el-option label="年份" value="year" />
        <el-option label="标题" value="title" />
      </el-select>
      <el-select v-model="sortDir" style="width: 110px;" @change="onFilterChanged">
        <el-option label="降序" value="desc" />
        <el-option label="升序" value="asc" />
      </el-select>
      <el-input
        v-model="searchQuery"
        placeholder="搜索文献"
        clearable
        style="width: 200px; margin-left: 0.5rem;"
        @keyup.enter="load"
      />
      <el-button @click="load">搜索</el-button>
      <el-button @click="openExternalSearch" :disabled="trashed">外部检索</el-button>
      <el-button @click="showBrowserCaptureDialog = true" :disabled="trashed">网页采集</el-button>
    </div>

    <div v-if="selectedIds.length" class="batch-actions">
      <span>已选 {{ selectedIds.length }} 条</span>
      <template v-if="!trashed">
        <el-button size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="showBatchReadStatus = true">批量阅读状态</el-button>
      </template>
      <template v-else>
        <el-button size="small" type="success" @click="batchRestore">批量恢复</el-button>
        <el-button size="small" type="danger" @click="batchPermanentDelete">批量永久删除</el-button>
      </template>
    </div>

    <el-table
      ref="tableRef"
      :data="papers"
      style="margin-top: 1rem;"
      @row-click="openDetail"
      @selection-change="onSelectionChange"
    >
      <el-table-column type="selection" width="45" />
      <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
      <el-table-column label="作者" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          {{ (parseAuthors(row.authors).map((a: any) => a.name).slice(0, 2).join('; ')) || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="year" label="年份" width="80" />
      <el-table-column label="阅读状态" width="96">
        <template #default="{ row }">
          <el-tag size="small" :type="readStatusTagType(row.read_status)">{{ readStatusLabel(row.read_status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="评分" width="110">
        <template #default="{ row }">
          <el-rate :model-value="Number(row.rating || 0)" disabled :max="5" />
        </template>
      </el-table-column>
      <el-table-column label="全文" width="108">
        <template #default="{ row }">
          <el-tag :type="fulltextTagType(row.fulltext_status)" size="small">
            {{ fulltextLabel(row.fulltext_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="!trashed" label="" width="100" align="center">
        <template #default="{ row }">
          <el-button
            v-if="row.fulltext_status !== 'full'"
            link
            type="primary"
            size="small"
            :loading="resolvingPaperId === row.id"
            @click.stop="onResolveFulltext(row)"
          >
            补全文
          </el-button>
          <span v-else class="muted tiny">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="添加时间" width="160" />
      <el-table-column v-if="trashed" label="操作" width="140" fixed="right" @click.stop>
        <template #default="{ row }">
          <el-button type="success" link size="small" @click.stop="restoreOne(row.id)">恢复</el-button>
          <el-button type="danger" link size="small" @click.stop="permanentDeleteOne(row.id)">永久删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > pageSize"
      v-model:current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="prev, pager, next"
      style="margin-top: 1rem;"
      @current-change="load"
    />

    <!-- 批量阅读状态 -->
    <el-dialog v-model="showBatchReadStatus" title="批量设置阅读状态" width="360px">
      <el-radio-group v-model="batchReadStatus">
        <el-radio value="unread">未读</el-radio>
        <el-radio value="reading">阅读中</el-radio>
        <el-radio value="read">已读</el-radio>
      </el-radio-group>
      <template #footer>
        <el-button @click="showBatchReadStatus = false">取消</el-button>
        <el-button type="primary" @click="doBatchReadStatus">确定</el-button>
      </template>
    </el-dialog>

    <!-- 外部多源检索 -->
    <el-dialog v-model="showExternalSearchDialog" title="检索外部文献（PubMed/CrossRef）" width="920px">
      <div class="translate-assist-bar">
        <span class="translate-assist-label">中译英辅助</span>
        <el-input
          v-model="translateInput"
          placeholder="输入中文关键词，如：糖尿病"
          style="width: 240px;"
          size="small"
          @keyup.enter="doTranslateKeyword"
        />
        <el-button size="small" type="primary" plain :loading="translateLoading" @click="doTranslateKeyword">翻译</el-button>
        <template v-if="translateOutput">
          <span class="translate-assist-result">{{ translateOutput }}</span>
          <el-button size="small" @click="useTranslateResult">用作关键词</el-button>
          <el-button size="small" text @click="appendTranslateResult">追加到关键词</el-button>
        </template>
        <span class="translate-assist-tip">PubMed 仅支持英文检索，中文关键词建议先翻译</span>
      </div>
      <el-form inline>
        <el-form-item label="关键词">
          <el-input v-model="externalQuery" placeholder="如：metformin type 2 diabetes" style="width: 300px;" @keyup.enter="doExternalSearch" />
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
        <el-form-item label="类型">
          <el-checkbox-group v-model="externalPubTypes">
            <el-checkbox value="guideline">指南</el-checkbox>
            <el-checkbox value="review">综述</el-checkbox>
            <el-checkbox value="meta">Meta分析</el-checkbox>
            <el-checkbox value="rct">临床试验</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="externalSearching" @click="doExternalSearch">检索</el-button>
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
      <div v-if="externalMetaText" class="empty-hint">{{ externalMetaText }}</div>
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
      <div class="external-search-body">
        <el-table :data="externalResults" max-height="360" @selection-change="onExternalSelectionChange" @row-click="onExternalRowClick">
          <el-table-column type="selection" width="40" />
          <el-table-column prop="title" label="标题" min-width="260" show-overflow-tooltip />
          <el-table-column prop="journal" label="期刊" min-width="160" show-overflow-tooltip />
          <el-table-column prop="year" label="年份" width="80" />
          <el-table-column label="来源" width="110">
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
        <div class="external-preview-panel">
          <template v-if="externalPreview">
            <div class="external-preview-title">{{ externalPreview.title }}</div>
            <div class="external-preview-meta">
              {{ (externalPreview.authors || []).map((a: any) => a.name).join('; ') || '-' }}
              · {{ externalPreview.journal || '-' }}
              · {{ externalPreview.year || '-' }}
            </div>
            <div class="external-preview-meta">来源：{{ (externalPreview._sources || [externalPreview.source]).join(', ') }}</div>
            <div class="external-preview-meta">
              状态：
              <el-tag size="small" :type="externalPreview.local_status === 'saved' ? 'success' : 'info'">
                {{ externalPreview.local_status === 'saved' ? '已入库' : '未入库' }}
              </el-tag>
              <span v-if="externalPreview.local_id">（本地 ID: {{ externalPreview.local_id }}）</span>
            </div>
            <div v-if="externalPreview.doi" class="external-preview-meta">DOI: {{ externalPreview.doi }}</div>
            <div v-if="externalPreview.abstract" class="external-preview-abstract">{{ externalPreview.abstract }}</div>
            <div v-else class="empty-hint">暂无摘要，点击结果可按需拉取</div>
            <div class="external-preview-actions">
              <el-button v-if="externalPreview.local_status === 'saved' && externalPreview.local_id" size="small" @click="openDetail({ id: externalPreview.local_id })">查看本地记录</el-button>
              <el-button v-else size="small" type="primary" :loading="externalSavingSingle" @click="saveExternalOne(externalPreview)">入库</el-button>
            </div>
          </template>
          <div v-else class="empty-hint">点击左侧结果可预览摘要</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showExternalSearchDialog = false">关闭</el-button>
        <el-button type="primary" :disabled="!externalSelected.length" :loading="externalSaving" @click="saveExternalSelected">批量入库</el-button>
      </template>
    </el-dialog>

    <!-- 新建集合 -->
    <el-dialog v-model="showCreateCollectionDialog" title="新建集合" width="360px" @closed="newCollectionName = ''">
      <el-form label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="newCollectionName" placeholder="如：心血管方向" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="父集合">
          <el-select v-model="newCollectionParentId" clearable placeholder="留空则为顶层" style="width: 100%;">
            <el-option v-for="c in flatCollections" :key="`newcoll-p-${c.id}`" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateCollectionDialog = false">取消</el-button>
        <el-button type="primary" :loading="creatingCollection" @click="doCreateCollection">创建</el-button>
      </template>
    </el-dialog>

    <!-- 新建标签 -->
    <el-dialog v-model="showCreateTagDialog" title="新建标签" width="360px" @closed="newTagName = ''">
      <el-form label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="newTagName" placeholder="如：meta分析" maxlength="30" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateTagDialog = false">取消</el-button>
        <el-button type="primary" :loading="creatingTag" @click="doCreateTag">创建</el-button>
      </template>
    </el-dialog>

    <!-- 浏览器采集联调 -->
    <el-dialog v-model="showBrowserCaptureDialog" title="网页采集（联调）" width="560px">
      <el-form label-width="90px">
        <el-form-item label="历史记录">
          <el-tag :type="captureHistoryEnabled ? 'success' : 'info'">
            {{ captureHistoryEnabled ? '已开启' : '已关闭' }}
          </el-tag>
          <el-button link type="primary" @click="goSettingsForPrivacy">去设置页修改</el-button>
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="browserCaptureForm.title" />
        </el-form-item>
        <el-form-item label="URL" required>
          <el-input v-model="browserCaptureForm.url" />
        </el-form-item>
        <el-form-item label="DOI">
          <el-input v-model="browserCaptureForm.doi" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="browserCaptureForm.abstract" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="选中文本">
          <el-input v-model="browserCaptureForm.selected_text" type="textarea" :rows="2" />
          <el-button link type="primary" @click="fillSelectedTextFromClipboard">从剪贴板填充</el-button>
        </el-form-item>
      </el-form>
      <div v-if="captureHistory.length" class="capture-result">
        <div class="capture-result-line">
          <strong>最近结果：</strong>
          <el-tag :type="captureHistory[0].status === 'created' ? 'success' : 'warning'">
            {{ captureHistory[0].status }}
          </el-tag>
          <span v-if="captureHistory[0].paperId">ID: {{ captureHistory[0].paperId }}</span>
          <span v-if="captureHistory[0].at">{{ captureHistory[0].at }}</span>
          <el-button link @click="clearCaptureHistory">清空</el-button>
        </div>
        <div class="capture-history-list">
          <div v-for="(item, idx) in captureHistory" :key="`${item.at}-${idx}`" class="capture-history-item">
            <el-tag size="small" :type="item.status === 'created' ? 'success' : 'warning'">{{ item.status }}</el-tag>
            <span v-if="item.paperId">ID: {{ item.paperId }}</span>
            <span>{{ item.at }}</span>
            <el-button v-if="item.paperId" link type="primary" @click="openCapturePaper(item.paperId)">打开</el-button>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="copyBrowserCapturePayload">复制请求体</el-button>
        <el-button @click="showBrowserCaptureDialog = false">取消</el-button>
        <el-button type="primary" :loading="browserCaptureSubmitting" @click="submitBrowserCapture">提交</el-button>
      </template>
    </el-dialog>

    <!-- 添加文献对话框 -->
    <el-dialog v-model="showAddDialog" title="添加文献" width="560px">
      <el-tabs v-model="addTab">
        <el-tab-pane label="DOI/PMID" name="doi">
          <el-form label-width="80px">
            <el-form-item label="DOI 或 PMID">
              <el-input v-model="doiOrPmid" placeholder="输入 DOI 或 PMID，点击拉取" />
            </el-form-item>
            <el-button :loading="fetching" @click="doFetchMetadata">拉取元数据</el-button>
            <template v-if="metadataPreview">
              <el-divider />
              <div class="meta-preview">
                <p><strong>标题：</strong>{{ metadataPreview.title }}</p>
                <p><strong>作者：</strong>{{ (metadataPreview.authors || []).map((a: any) => a.name).join('; ') }}</p>
                <p><strong>期刊：</strong>{{ metadataPreview.journal }}</p>
                <p><strong>年份：</strong>{{ metadataPreview.year }}</p>
              </div>
              <el-form-item label="集合">
                <el-select v-model="addCollectionId" clearable style="width: 100%;">
                  <el-option v-for="c in flatCollections" :key="`add-c-${c.id}`" :label="c.name" :value="c.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="标签">
                <el-select v-model="addTagIds" multiple clearable style="width: 100%;">
                  <el-option v-for="t in tags" :key="`add-t-${t.id}`" :label="t.name" :value="t.id" />
                </el-select>
              </el-form-item>
              <div v-if="dupHint" class="dup-box">
                ⚠️ 相似文献提示（相似度 {{ Math.round((dupHint.similarity || 0) * 100) }}%）：
                <div class="dup-title">"{{ dupHint.title || '未知标题' }}"</div>
              </div>
              <el-button type="primary" @click="createFromMetadata">添加文献</el-button>
            </template>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="手动录入" name="manual">
          <el-form label-width="80px">
            <el-form-item label="标题" required>
              <el-input v-model="manualForm.title" />
            </el-form-item>
            <el-form-item label="作者">
              <el-input v-model="manualForm.authorsText" placeholder="多个作者用分号分隔" />
            </el-form-item>
            <el-form-item label="期刊">
              <el-input v-model="manualForm.journal" />
            </el-form-item>
            <el-form-item label="年份">
              <el-input-number v-model="manualForm.year" :min="1900" :max="2030" />
            </el-form-item>
            <el-form-item label="DOI">
              <el-input v-model="manualForm.doi" />
            </el-form-item>
            <el-form-item label="摘要">
              <el-input v-model="manualForm.abstract" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item label="集合">
              <el-select v-model="addCollectionId" clearable style="width: 100%;">
                <el-option v-for="c in flatCollections" :key="`manual-c-${c.id}`" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="标签">
              <el-select v-model="addTagIds" multiple clearable style="width: 100%;">
                <el-option v-for="t in tags" :key="`manual-t-${t.id}`" :label="t.name" :value="t.id" />
              </el-select>
            </el-form-item>
            <el-button type="primary" @click="createManual">添加</el-button>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="文件导入" name="file">
          <el-form label-width="90px">
            <el-form-item label="导入文件">
              <el-upload
                :show-file-list="true"
                accept=".pdf,.ris,.bib,.bibtex"
                :limit="1"
                :before-upload="(file: File) => { importFromDialog(file); return false }"
              >
                <el-button :loading="importPolling">选择文件并导入</el-button>
              </el-upload>
            </el-form-item>
            <div class="empty-hint">支持 PDF / RIS / BibTeX，导入完成后自动刷新列表。</div>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { api, API_BASE, getAuthToken, getLocalApiKeyHeaderForFetch } from '@/api'
import { AUTH_USER_CHANGED_EVENT } from '@/stores/auth'

function parseAuthors(v: any): any[] {
  if (Array.isArray(v)) return v
  if (typeof v === 'string') {
    try { const p = JSON.parse(v); if (Array.isArray(p)) return p } catch {}
  }
  return []
}

const papers = ref<any[]>([])
const router = useRouter()
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const trashed = ref(false)
const totalAll = ref(0)
const totalUnread = ref(0)
const totalTrash = ref(0)
const activeCollectionId = ref<number | null>(null)
const activeTagId = ref<number | null>(null)
const readStatusFilter = ref<'unread' | 'reading' | 'read' | ''>('')
const sortBy = ref<'created_at' | 'year' | 'title'>('created_at')
const sortDir = ref<'asc' | 'desc'>('desc')
const collections = ref<any[]>([])
const tags = ref<any[]>([])
const selectedIds = ref<number[]>([])
const tableRef = ref<any>(null)
const showBatchReadStatus = ref(false)
const batchReadStatus = ref<'unread' | 'reading' | 'read'>('unread')
const showCreateCollectionDialog = ref(false)
const showCreateTagDialog = ref(false)
const newCollectionName = ref('')
const newCollectionParentId = ref<number | null>(null)
const newTagName = ref('')
const creatingCollection = ref(false)
const creatingTag = ref(false)
const showBrowserCaptureDialog = ref(false)
const browserCaptureSubmitting = ref(false)
const captureHistory = ref<Array<{ status: string; paperId?: number; at: string }>>([])
const browserCaptureForm = ref({
  title: '',
  url: '',
  doi: '',
  abstract: '',
  selected_text: '',
})
const showAddDialog = ref(false)
const showExternalSearchDialog = ref(false)
const externalQuery = ref('')
const externalSources = ref<Array<'pubmed' | 'crossref' | 'semantic_scholar'>>(['pubmed', 'crossref'])
const externalYearFrom = ref<number | null>(null)
const externalYearTo = ref<number | null>(null)
const externalLanguage = ref<'all' | 'en' | 'zh'>('all')
const externalPubTypes = ref<Array<'guideline' | 'review' | 'meta' | 'rct'>>([])
const externalSearching = ref(false)
const externalSaving = ref(false)
const externalSavingSingle = ref(false)
const externalResults = ref<any[]>([])
const externalSelected = ref<any[]>([])
const externalMetaText = ref('')
const externalSourceStats = ref<Array<{ id: string; count: number; elapsed: number; error?: string; progress: number; status: 'running' | 'done' | 'error'; stageText?: string }>>([])
let externalProgressTimer: number | null = null
const externalPreview = ref<any | null>(null)
const translateInput = ref('')
const translateOutput = ref('')
const translateLoading = ref(false)
const addTab = ref('doi')
const doiOrPmid = ref('')
const fetching = ref(false)
const metadataPreview = ref<any>(null)
const dupHint = ref<any>(null)
const addCollectionId = ref<number | null>(null)
const addTagIds = ref<number[]>([])
const importPolling = ref(false)
const resolvingPaperId = ref<number | null>(null)
const manualForm = ref({
  title: '',
  authorsText: '',
  journal: '',
  year: null as number | null,
  doi: '',
  abstract: '',
})

const CAPTURE_HISTORY_KEY = 'literature_browser_capture_history_v1'
const CAPTURE_HISTORY_ENABLED_KEY = 'literature_browser_capture_history_enabled_v1'
const captureHistoryEnabled = ref(true)

async function load() {
  try {
    const res = await api.literature.getPapers({
      q: searchQuery.value || undefined,
      page: page.value,
      page_size: pageSize.value,
      trashed: trashed.value,
      read_status: readStatusFilter.value || undefined,
      collection_id: activeCollectionId.value || undefined,
      tag_ids: activeTagId.value ? [activeTagId.value] : undefined,
      sort_by: sortBy.value,
      sort_dir: sortDir.value,
    })
    const data = res.data as any
    papers.value = data?.items || []
    total.value = data?.total ?? 0
  } catch {
    papers.value = []
    total.value = 0
  }
}

async function loadSidebarData() {
  try {
    const [collRes, tagRes] = await Promise.all([
      api.literature.getCollections(),
      api.literature.getTags(),
    ])
    collections.value = Array.isArray(collRes.data) ? collRes.data : []
    tags.value = Array.isArray(tagRes.data) ? tagRes.data : []
  } catch {
    collections.value = []
    tags.value = []
  }
}

async function loadCounters() {
  try {
    const [allRes, unreadRes, trashRes] = await Promise.all([
      api.literature.getPapers({ page: 1, page_size: 1, trashed: false }),
      api.literature.getPapers({ page: 1, page_size: 1, trashed: false, read_status: 'unread' }),
      api.literature.getPapers({ page: 1, page_size: 1, trashed: true }),
    ])
    totalAll.value = Number((allRes.data as any)?.total || 0)
    totalUnread.value = Number((unreadRes.data as any)?.total || 0)
    totalTrash.value = Number((trashRes.data as any)?.total || 0)
  } catch {
    totalAll.value = 0
    totalUnread.value = 0
    totalTrash.value = 0
  }
}

const flatCollections = computed(() => {
  const out: Array<{ id: number; name: string; count: number; depth: number }> = []
  const walk = (nodes: any[], depth: number) => {
    for (const n of nodes || []) {
      out.push({ id: n.id, name: n.name, count: n.count || 0, depth })
      if (Array.isArray(n.children) && n.children.length) walk(n.children, depth + 1)
    }
  }
  walk(collections.value, 0)
  return out
})

function resetSidebarFilters(toTrash: boolean) {
  trashed.value = toTrash
  activeCollectionId.value = null
  activeTagId.value = null
  readStatusFilter.value = ''
  page.value = 1
  load()
}

function setReadStatusFilter(v: 'unread' | 'reading' | 'read') {
  trashed.value = false
  activeCollectionId.value = null
  activeTagId.value = null
  readStatusFilter.value = v
  page.value = 1
  load()
}

function selectCollection(id: number) {
  trashed.value = false
  activeCollectionId.value = id
  activeTagId.value = null
  page.value = 1
  load()
}

function selectTag(id: number) {
  trashed.value = false
  activeTagId.value = id
  activeCollectionId.value = null
  page.value = 1
  load()
}

async function doCreateCollection() {
  const name = newCollectionName.value?.trim()
  if (!name) {
    ElMessage.warning('请输入集合名称')
    return
  }
  creatingCollection.value = true
  try {
    await api.literature.createCollection({
      name,
      parent_id: newCollectionParentId.value || undefined,
    })
    ElMessage.success('创建成功')
    showCreateCollectionDialog.value = false
    newCollectionName.value = ''
    newCollectionParentId.value = null
    await loadSidebarData()
  } catch (e: any) {
    const d = e?.response?.data?.detail
    ElMessage.error(typeof d === 'string' ? d : '创建失败')
  } finally {
    creatingCollection.value = false
  }
}

async function doCreateTag() {
  const name = newTagName.value?.trim()
  if (!name) {
    ElMessage.warning('请输入标签名称')
    return
  }
  creatingTag.value = true
  try {
    await api.literature.createTag({ name })
    ElMessage.success('创建成功')
    showCreateTagDialog.value = false
    newTagName.value = ''
    await loadSidebarData()
  } catch (e: any) {
    const d = e?.response?.data?.detail
    ElMessage.error(typeof d === 'string' ? d : '创建失败')
  } finally {
    creatingTag.value = false
  }
}

function onFilterChanged() {
  page.value = 1
  load()
}

function onTrashedChange() {
  selectedIds.value = []
  page.value = 1
  load()
}

function onSelectionChange(rows: any[]) {
  selectedIds.value = (rows || []).map((r: any) => r.id).filter(Boolean)
}

async function batchDelete() {
  if (!selectedIds.value.length) return
  try {
    await ElMessageBox.confirm(`确定将选中的 ${selectedIds.value.length} 条文献移入回收站？`)
  } catch { return }
  try {
    await api.literature.batchOperation({
      operation: 'delete',
      paper_ids: selectedIds.value,
    })
    ElMessage.success('已移入回收站')
    selectedIds.value = []
    tableRef.value?.clearSelection?.()
    load()
    loadCounters()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

async function batchRestore() {
  if (!selectedIds.value.length) return
  try {
    await api.literature.batchOperation({
      operation: 'restore',
      paper_ids: selectedIds.value,
    })
    ElMessage.success('已恢复')
    selectedIds.value = []
    tableRef.value?.clearSelection?.()
    load()
    loadCounters()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

async function batchPermanentDelete() {
  if (!selectedIds.value.length) return
  try {
    await ElMessageBox.confirm(
      `确定永久删除选中的 ${selectedIds.value.length} 条文献？此操作不可恢复。`,
      '警告',
      { type: 'warning' }
    )
  } catch { return }
  try {
    await api.literature.batchOperation({
      operation: 'permanent',
      paper_ids: selectedIds.value,
    })
    ElMessage.success('已永久删除')
    selectedIds.value = []
    tableRef.value?.clearSelection?.()
    load()
    loadCounters()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

async function doBatchReadStatus() {
  if (!selectedIds.value.length) return
  try {
    await api.literature.batchOperation({
      operation: 'read_status',
      paper_ids: selectedIds.value,
      payload: { status: batchReadStatus.value },
    })
    ElMessage.success('已更新阅读状态')
    showBatchReadStatus.value = false
    selectedIds.value = []
    tableRef.value?.clearSelection?.()
    load()
    loadCounters()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

async function submitBrowserCapture() {
  const form = browserCaptureForm.value
  if (!form.title.trim() || !form.url.trim()) {
    ElMessage.warning('请填写标题和 URL')
    return
  }
  const urlValue = form.url.trim()
  const doiValue = normalizeDoiInput(form.doi)
  form.url = urlValue
  form.doi = doiValue
  if (!isValidHttpUrl(urlValue)) {
    ElMessage.warning('URL 格式不正确，请输入 http/https 地址')
    return
  }
  if (doiValue && !isLikelyDoi(doiValue)) {
    ElMessage.warning('DOI 格式不正确，请检查后重试')
    return
  }
  browserCaptureSubmitting.value = true
  try {
    const res = await api.literature.browserCapture(buildBrowserCapturePayload())
    const data = res.data as any
    if (data?.status === 'duplicate') {
      ElMessage.warning(`已存在重复文献（ID: ${data.existing_id}）`)
      pushCaptureHistory({
        status: 'duplicate',
        paperId: Number(data.existing_id) || undefined,
        at: new Date().toLocaleTimeString(),
      })
    } else if (data?.status === 'created') {
      ElMessage.success(`采集成功（ID: ${data.paper_id}）`)
      pushCaptureHistory({
        status: 'created',
        paperId: Number(data.paper_id) || undefined,
        at: new Date().toLocaleTimeString(),
      })
      await load()
      const target = papers.value.find((p: any) => p.id === data.paper_id)
      if (target) {
        await openDetail(target)
      } else {
        try {
          const res = await api.literature.getPaper(data.paper_id)
          if (res?.data) await openDetail(res.data)
        } catch {
          // ignore fallback open errors
        }
      }
    } else {
      ElMessage.success('采集完成')
      pushCaptureHistory({
        status: String(data?.status || 'ok'),
        at: new Date().toLocaleTimeString(),
      })
      await load()
    }
    showBrowserCaptureDialog.value = false
    browserCaptureForm.value = { title: '', url: '', doi: '', abstract: '', selected_text: '' }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '采集失败')
  } finally {
    browserCaptureSubmitting.value = false
  }
}

function pushCaptureHistory(item: { status: string; paperId?: number; at: string }) {
  if (!captureHistoryEnabled.value) return
  captureHistory.value.unshift(item)
  if (captureHistory.value.length > 5) {
    captureHistory.value = captureHistory.value.slice(0, 5)
  }
  persistCaptureHistory()
}

function clearCaptureHistory() {
  captureHistory.value = []
  persistCaptureHistory()
}

function persistCaptureHistory() {
  if (!captureHistoryEnabled.value) return
  try {
    localStorage.setItem(CAPTURE_HISTORY_KEY, JSON.stringify(captureHistory.value))
  } catch {
    // ignore persistence failures
  }
}

function restoreCaptureHistory() {
  try {
    const enabledRaw = localStorage.getItem(CAPTURE_HISTORY_ENABLED_KEY)
    if (enabledRaw === '0') {
      captureHistoryEnabled.value = false
      captureHistory.value = []
      return
    }
    const raw = localStorage.getItem(CAPTURE_HISTORY_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return
    captureHistory.value = parsed
      .filter((x: any) => x && typeof x.status === 'string' && typeof x.at === 'string')
      .slice(0, 5)
      .map((x: any) => ({
        status: x.status,
        paperId: typeof x.paperId === 'number' ? x.paperId : undefined,
        at: x.at,
      }))
  } catch {
    // ignore restore failures
  }
}

watch(captureHistoryEnabled, (enabled) => {
  try {
    localStorage.setItem(CAPTURE_HISTORY_ENABLED_KEY, enabled ? '1' : '0')
  } catch {
    // ignore write failures
  }
  if (!enabled) {
    captureHistory.value = []
    try {
      localStorage.removeItem(CAPTURE_HISTORY_KEY)
    } catch {
      // ignore remove failures
    }
  }
})

function goSettingsForPrivacy() {
  showBrowserCaptureDialog.value = false
  window.location.hash = '#/settings'
}

async function openCapturePaper(paperId?: number) {
  if (!paperId) return
  try {
    const target = papers.value.find((p: any) => p.id === paperId)
    if (target) {
      await openDetail(target)
      return
    }
    const res = await api.literature.getPaper(paperId)
    if (res?.data) await openDetail(res.data)
  } catch {
    ElMessage.error('打开文献失败')
  }
}

function buildBrowserCapturePayload() {
  const form = browserCaptureForm.value
  return {
    title: form.title.trim(),
    url: form.url.trim(),
    doi: normalizeDoiInput(form.doi) || undefined,
    abstract: form.abstract.trim() || undefined,
    selected_text: form.selected_text.trim() || undefined,
  }
}

async function copyBrowserCapturePayload() {
  try {
    const payload = buildBrowserCapturePayload()
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2))
    ElMessage.success('已复制请求体')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

function isValidHttpUrl(value: string): boolean {
  try {
    const u = new URL(value)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

function isLikelyDoi(value: string): boolean {
  const v = normalizeDoiInput(value)
  return /^10\.\d{4,9}\/\S+$/.test(v)
}

function normalizeDoiInput(value: string): string {
  return (value || '')
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\/doi\.org\//, '')
}

async function fillSelectedTextFromClipboard() {
  try {
    const text = await navigator.clipboard.readText()
    if (!text?.trim()) {
      ElMessage.warning('剪贴板为空')
      return
    }
    browserCaptureForm.value.selected_text = text.trim()
    ElMessage.success('已填充选中文本')
  } catch {
    ElMessage.error('读取剪贴板失败，请手动粘贴')
  }
}

async function restoreOne(id: number) {
  try {
    await api.literature.restorePaper(id)
    ElMessage.success('已恢复')
    load()
    loadCounters()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

async function permanentDeleteOne(id: number) {
  try {
    await ElMessageBox.confirm('确定永久删除该文献？此操作不可恢复。', '警告', { type: 'warning' })
  } catch { return }
  try {
    await api.literature.permanentDeletePaper(id)
    ElMessage.success('已永久删除')
    load()
    loadCounters()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

async function handleImport(file: any) {
  const form = new FormData()
  form.append('file', file.raw)
  try {
    const res = await api.literature.importPapers(form) as any
    const d = res.data
    if (d?.task_id) {
      importPolling.value = true
      ElMessage.info(`已创建导入任务（共 ${d?.total ?? 0} 条），正在后台处理...`)
      await pollImportTask(d.task_id)
      return
    }
    showImportResult(d)
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '导入失败')
  } finally {
    importPolling.value = false
  }
}

async function importFromDialog(file: File) {
  const form = new FormData()
  form.append('file', file)
  try {
    const res = await api.literature.importPapers(form) as any
    const d = res.data
    if (d?.task_id) {
      importPolling.value = true
      ElMessage.info(`已创建导入任务（共 ${d?.total ?? 0} 条），正在后台处理...`)
      await pollImportTask(d.task_id)
      return
    }
    showImportResult(d)
    showAddDialog.value = false
    await load()
    await loadCounters()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '导入失败')
  } finally {
    importPolling.value = false
  }
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function showImportResult(d: any) {
  const success = d?.success ?? 0
  const skipped = d?.skipped ?? 0
  const failed = d?.failed ?? 0
  ElMessage.success(`导入完成：成功 ${success} 条，跳过 ${skipped} 条，失败 ${failed} 条`)
  const errs = Array.isArray(d?.errors) ? d.errors : []
  if (errs.length) {
    const preview = errs.slice(0, 5).map((e: any) => `#${e.index ?? '-'} ${e.title || '未命名'}：${e.message || e.code || '失败'}`)
    ElMessageBox.alert(preview.join('\n'), `导入异常明细（共 ${errs.length} 条，仅展示前 5 条）`, {
      confirmButtonText: '知道了',
      type: 'warning',
    })
  }
}

async function pollImportTask(taskId: string) {
  for (let i = 0; i < 120; i++) {
    const res = await api.literature.getImportTask(taskId)
    const task = res.data as any
    if (task?.status === 'done') {
      showImportResult(task?.result || {})
      await load()
      return
    }
    if (task?.status === 'failed') {
      ElMessage.error(task?.error || '导入任务失败')
      return
    }
    await sleep(1500)
  }
  ElMessage.warning('导入任务仍在处理中，请稍后重试查看结果')
}

async function handleFileChange(file: any) {
  const form = new FormData()
  form.append('file', file.raw)
  try {
    await api.literature.uploadPaper(form)
    ElMessage.success('上传成功')
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '上传失败')
  }
}

async function doFetchMetadata() {
  const v = doiOrPmid.value?.trim()
  if (!v) {
    ElMessage.warning('请输入 DOI 或 PMID')
    return
  }
  fetching.value = true
  metadataPreview.value = null
  dupHint.value = null
  try {
    const isPmid = /^\d+$/.test(v)
    const res = await api.literature.fetchMetadata(isPmid ? { pmid: v } : { doi: v })
    metadataPreview.value = res.data
    const m = res.data as any
    const dupRes = await api.literature.checkDuplicate({
      doi: m?.doi,
      title: m?.title || '',
      authors: m?.authors || [],
      year: m?.year,
    })
    const dup = dupRes.data as any
    if (!dup?.exact_match && Array.isArray(dup?.fuzzy_matches) && dup.fuzzy_matches.length) {
      dupHint.value = dup.fuzzy_matches[0]
    }
  } catch (e: any) {
    const d = e?.response?.data?.detail
    ElMessage.error(typeof d === 'object' ? d?.message || '拉取失败' : '拉取失败')
  } finally {
    fetching.value = false
  }
}

async function createFromMetadata() {
  const m = metadataPreview.value
  if (!m?.title) return
  try {
    await api.literature.createPaper({
      title: m.title,
      authors: m.authors || [],
      journal: m.journal || '',
      year: m.year,
      doi: m.doi,
      pmid: m.pmid,
      abstract: m.abstract || '',
      keywords: m.keywords || [],
      collection_id: addCollectionId.value || undefined,
      tag_ids: addTagIds.value,
    })
    ElMessage.success('添加成功')
    showAddDialog.value = false
    doiOrPmid.value = ''
    metadataPreview.value = null
    dupHint.value = null
    await load()
    await loadCounters()
  } catch (e: any) {
    const d = e?.response?.data?.detail
    if (typeof d === 'object' && d?.code === 'DUPLICATE_DOI') {
      ElMessage.warning(`已存在相同 DOI 的文献 (ID: ${d.existing_id})`)
    } else {
      ElMessage.error('添加失败')
    }
  }
}

async function createManual() {
  if (!manualForm.value.title?.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  const authors = (manualForm.value.authorsText || '')
    .split(/[;；]/)
    .map((n: string) => ({ name: n.trim(), affil: '' }))
    .filter((a: any) => a.name)
  try {
    await api.literature.createPaper({
      title: manualForm.value.title,
      authors,
      journal: manualForm.value.journal || '',
      year: manualForm.value.year || undefined,
      doi: manualForm.value.doi || undefined,
      abstract: manualForm.value.abstract || '',
      collection_id: addCollectionId.value || undefined,
      tag_ids: addTagIds.value,
    })
    ElMessage.success('添加成功')
    showAddDialog.value = false
    manualForm.value = { title: '', authorsText: '', journal: '', year: null, doi: '', abstract: '' }
    addCollectionId.value = null
    addTagIds.value = []
    await load()
    await loadCounters()
  } catch (e: any) {
    ElMessage.error('添加失败')
  }
}

async function openDetail(row: any) {
  const id = Number(row?.id || 0)
  if (!id) return
  await router.push({ name: 'literature-paper', params: { paperId: id } })
}

function readStatusLabel(s: string) {
  if (s === 'reading') return '在读'
  if (s === 'read') return '已读'
  return '未读'
}

function readStatusTagType(s: string) {
  if (s === 'reading') return 'warning'
  if (s === 'read') return 'success'
  return 'info'
}

function fulltextLabel(s: string | undefined) {
  if (s === 'full') return '全文就绪'
  if (s === 'pending') return '获取中'
  if (s === 'no_fulltext') return '缺全文'
  return '获取中'
}

function fulltextTagType(s: string | undefined) {
  if (s === 'full') return 'success'
  if (s === 'no_fulltext') return 'danger'
  return 'warning'
}

async function onResolveFulltext(row: any) {
  const id = Number(row?.id || 0)
  if (!id) return
  resolvingPaperId.value = id
  try {
    await api.literature.resolveFulltext(id)
    ElMessage.success('已排队获取全文，稍候自动刷新状态')
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 2000))
      const res = await api.literature.getPaper(id)
      const st = (res.data as any)?.fulltext_status
      const idx = papers.value.findIndex((p: any) => p.id === id)
      if (idx >= 0) {
        papers.value[idx] = { ...papers.value[idx], ...(res.data as any) }
      }
      if (st === 'full') {
        ElMessage.success('全文已就绪')
        break
      }
      if (st === 'no_fulltext' && i > 2) {
        ElMessage.warning('暂无法自动获取全文，请上传 PDF 或核对 DOI/PMID')
        break
      }
    }
    await load()
    await loadCounters()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '请求失败')
  } finally {
    resolvingPaperId.value = null
  }
}

function openExternalSearch() {
  showExternalSearchDialog.value = true
  if (!externalQuery.value) externalQuery.value = searchQuery.value || ''
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

function onExternalSelectionChange(rows: any[]) {
  externalSelected.value = rows || []
}

async function doExternalSearch() {
  const q = externalQuery.value.trim()
  if (!q) {
    ElMessage.warning('请输入关键词')
    return
  }
  if (!externalSources.value.length) {
    ElMessage.warning('请至少选择一个数据源')
    return
  }
  externalSearching.value = true
  externalMetaText.value = ''
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
      // 流式失败回退普通检索
      const res = await api.literature.searchExternal(payload)
      finalData = res.data
    }
    externalResults.value = finalData?.results || []
    externalPreview.value = externalResults.value[0] || null
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
    const policyMap: Record<string, string> = { query_tag: '查询标签', metadata: '元数据', heuristic: '启发式', none: '无' }
    const counts = Object.keys(src).map((k) => `${k}:${src[k]?.count ?? 0}`).join('，')
    const policies = Object.keys(src).map((k) => `${k}:${policyMap[src[k]?.language_policy || 'none']}`).join('，')
    externalMetaText.value = `共 ${finalData?.total ?? 0} 条；${counts}` + (externalLanguage.value !== 'all' ? `；语言策略：${policies}` : '')
  } catch (e: any) {
    externalResults.value = []
    externalPreview.value = null
    externalMetaText.value = ''
    externalSourceStats.value = []
    ElMessage.error(e?.response?.data?.detail || '检索失败')
  } finally {
    if (externalProgressTimer) {
      window.clearInterval(externalProgressTimer)
      externalProgressTimer = null
    }
    externalSearching.value = false
  }
}

async function onExternalRowClick(row: any) {
  externalPreview.value = row
  if (!row?.abstract && (row?.pmid || row?.doi)) {
    try {
      const params = row?.pmid ? { pmid: String(row.pmid) } : { doi: String(row.doi) }
      const res = await api.literature.fetchSearchAbstract(params)
      const abs = res?.data?.abstract || ''
      if (abs) {
        row.abstract = abs
        if (externalPreview.value && externalPreview.value.source_id === row.source_id) {
          externalPreview.value = { ...row }
        }
      }
    } catch {
      // ignore preview fetch error
    }
  }
}

async function saveExternalSelected() {
  if (!externalSelected.value.length) return
  externalSaving.value = true
  try {
    const items = externalSelected.value.map((r: any) => ({
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
    }))
    const ret = await api.literature.saveSearchResults({
      items,
      collection_id: addCollectionId.value || undefined,
      tag_ids: addTagIds.value || [],
    })
    ElMessage.success(`入库完成：新建 ${ret.data?.created || 0}，跳过 ${ret.data?.skipped || 0}`)
    await load()
    await loadCounters()
    await loadSidebarData()
    externalSelected.value = []
    await doExternalSearch()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '入库失败')
  } finally {
    externalSaving.value = false
  }
}

async function saveExternalOne(row: any) {
  if (!row) return
  externalSavingSingle.value = true
  try {
    const item = {
      source: row.source,
      source_id: row.source_id || '',
      title: row.title || '',
      authors: (row.authors || []).map((a: any) => ({ name: a.name || '', affil: a.affil || '' })),
      journal: row.journal || '',
      year: row.year || null,
      volume: row.volume || '',
      issue: row.issue || '',
      pages: row.pages || '',
      doi: row.doi || null,
      pmid: row.pmid || null,
      url: row.url || '',
      abstract: row.abstract || '',
      pub_types: row.pub_types || [],
      cite_count: row.cite_count || 0,
      open_access_url: row.open_access_url || '',
    }
    const ret = await api.literature.saveSearchResults({
      items: [item],
      collection_id: addCollectionId.value || undefined,
      tag_ids: addTagIds.value || [],
    })
    if ((ret.data?.created || 0) > 0) {
      ElMessage.success('已入库')
      await load()
      await loadCounters()
      await loadSidebarData()
      await doExternalSearch()
    } else {
      ElMessage.info('已存在，跳过入库')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '入库失败')
  } finally {
    externalSavingSingle.value = false
  }
}

async function onApiKeyCommand(cmd: string) {
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

onMounted(async () => {
  restoreCaptureHistory()
  await loadSidebarData()
  await loadCounters()
  await load()
  window.addEventListener(AUTH_USER_CHANGED_EVENT, handleAuthUserChanged as EventListener)
})

onUnmounted(() => {
  window.removeEventListener(AUTH_USER_CHANGED_EVENT, handleAuthUserChanged as EventListener)
})

async function handleAuthUserChanged() {
  await loadSidebarData()
  await loadCounters()
  await load()
  if (showExternalSearchDialog.value && externalQuery.value.trim()) {
    await doExternalSearch()
  }
}
</script>

<style scoped>
.literature-index { padding: 1.5rem; }
h2 { margin-bottom: 1rem; }
.page-layout { display: flex; gap: 1rem; }
.sidebar { width: 240px; flex-shrink: 0; border-right: 1px solid var(--el-border-color); padding-right: 1rem; }
.side-block { margin-bottom: 1rem; }
.side-title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem; }
.side-title-row .side-title { font-size: 12px; color: var(--el-text-color-secondary); }
.side-title { font-size: 12px; color: var(--el-text-color-secondary); margin-bottom: 0.35rem; }
.side-nav-item { cursor: pointer; padding: 0.35rem 0; font-size: 14px; border-radius: 4px; }
.side-nav-item:hover { background: var(--el-fill-color-light); }
.side-nav-item.active { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.side-nav-item span { color: var(--el-text-color-secondary); margin-left: 4px; }
.main-panel { flex: 1; min-width: 0; }
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; }
.batch-actions { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.5rem; padding: 0.5rem; background: var(--el-fill-color-light); border-radius: 4px; }
.meta-preview { margin: 1rem 0; padding: 0.5rem; background: var(--el-fill-color-light); border-radius: 4px; }
.meta-preview p { margin: 0.25rem 0; }
:deep(.el-table__row) { cursor: pointer; }
.capture-result { margin-top: 8px; padding: 8px; border-radius: 4px; background: var(--el-fill-color-light); }
.capture-result-line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.capture-history-list { margin-top: 6px; display: flex; flex-direction: column; gap: 4px; }
.capture-history-item { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.empty-hint { color: var(--el-text-color-placeholder); font-size: 0.9em; margin: 0.5rem 0; }
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
  max-width: 320px;
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
.external-search-body { display: flex; gap: 12px; align-items: stretch; }
.external-search-body :deep(.el-table) { flex: 1; min-width: 0; }
.external-preview-panel {
  width: 290px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background: #fff;
  padding: 10px;
  overflow: auto;
  max-height: 360px;
}
.external-preview-title { font-weight: 600; margin-bottom: 6px; line-height: 1.4; }
.external-preview-meta { color: var(--el-text-color-secondary); font-size: 12px; margin-bottom: 6px; }
.external-preview-abstract { margin-top: 8px; white-space: pre-wrap; line-height: 1.5; font-size: 13px; }
.external-preview-actions { margin-top: 10px; display: flex; gap: 8px; }
.source-stats-row { display: flex; gap: 8px; margin: 6px 0 8px; }
.source-stat-card { border: 1px solid var(--el-border-color); border-radius: 6px; padding: 6px 8px; min-width: 140px; background: #fff; }
.source-stat-title { font-weight: 600; margin-bottom: 4px; }
.source-stat-line { font-size: 12px; color: var(--el-text-color-secondary); }
.source-stat-ok { font-size: 12px; color: var(--el-color-success); margin-top: 2px; }
.source-stat-error { font-size: 12px; color: var(--el-color-danger); margin-top: 2px; }
.dup-box {
  margin: 8px 0;
  padding: 8px 10px;
  border: 1px solid #f3d19e;
  border-radius: 6px;
  background: #fdf6ec;
  color: #8a5a12;
}
.dup-title { margin-top: 4px; font-weight: 600; }
.muted { color: var(--el-text-color-secondary); }
.tiny { font-size: 12px; }
</style>
