<script setup lang="ts">
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  FileText,
  Filter,
  PanelLeftClose,
  PanelLeftOpen,
  PencilLine,
  Search,
} from "lucide-vue-next";
import { computed } from "vue";
import type { ChunkSummary, TaskInfo } from "../types";

const props = defineProps<{
  task: TaskInfo | null;
  chunks: ChunkSummary[];
  filteredChunks: ChunkSummary[];
  activeChunkId: string;
  selectedPdf: string;
  searchQuery: string;
  pendingOnly: boolean;
  collapsed: boolean;
  documentPercent: number;
  statusLabel: (chunk: ChunkSummary) => string;
}>();

const emit = defineEmits<{
  "update:selectedPdf": [value: string];
  "update:searchQuery": [value: string];
  "update:pendingOnly": [value: boolean];
  "update:collapsed": [value: boolean];
  selectChunk: [chunkId: string];
  clearFilters: [];
}>();

const documentOptions = computed(() => {
  const values = new Map<string, { total: number; approved: number }>();
  for (const chunk of props.chunks) {
    const title = chunk._source_title || "未命名文档";
    const stats = values.get(title) || { total: 0, approved: 0 };
    stats.total += 1;
    if (chunk.approved) stats.approved += 1;
    values.set(title, stats);
  }
  return Array.from(values, ([title, stats]) => ({ title, ...stats })).sort((a, b) =>
    a.title.localeCompare(b.title, "zh-CN"),
  );
});

const currentDocument = computed(() =>
  documentOptions.value.find((item) => item.title === props.selectedPdf),
);
</script>

<template>
  <aside class="chunk-sidebar" :class="{ collapsed }">
    <template v-if="!collapsed">
      <div class="sidebar-overview">
        <div class="overview-head">
          <div>
            <span class="eyebrow">复验进度</span>
            <strong>{{ task?.progress.approved }}/{{ task?.progress.total }}</strong>
          </div>
          <button
            class="icon-button subtle"
            type="button"
            aria-label="折叠 Chunk 导航"
            @click="emit('update:collapsed', true)"
          >
            <PanelLeftClose :size="18" />
          </button>
        </div>
        <div class="progress-track" aria-label="全篇复验进度">
          <div class="progress-value" :style="{ width: `${documentPercent}%` }"></div>
        </div>
        <div class="overview-meta">
          <span>{{ documentPercent }}% 已完成</span>
          <span v-if="task?.progress.issues" class="issue-text">
            <AlertCircle :size="13" />{{ task.progress.issues }} 项需处理
          </span>
          <span v-else><CheckCircle2 :size="13" />暂无阻塞</span>
        </div>
      </div>

      <div class="document-picker">
        <span class="eyebrow">文档范围</span>
        <label class="document-select">
          <FileText :size="15" />
          <span>
            <select
              :value="selectedPdf"
              aria-label="选择复验文档"
              @change="emit('update:selectedPdf', ($event.target as HTMLSelectElement).value)"
            >
              <option value="">全部文档（{{ chunks.length }} 段）</option>
              <option v-for="item in documentOptions" :key="item.title" :value="item.title">
                {{ item.title.replace(/\u300a|\u300b/g, "") }}（{{ item.total }} 段）
              </option>
            </select>
            <small v-if="currentDocument">
              {{ currentDocument.approved }}/{{ currentDocument.total }} 已通过
            </small>
            <small v-else>{{ chunks.filter((item) => item.approved).length }}/{{ chunks.length }} 已通过</small>
          </span>
          <ChevronDown :size="15" />
        </label>
      </div>

      <div class="chunk-tools">
        <label class="search-field">
          <Search :size="15" />
          <input
            :value="searchQuery"
            type="search"
            placeholder="搜索章节或原文"
            @input="emit('update:searchQuery', ($event.target as HTMLInputElement).value)"
          />
        </label>
        <button
          class="filter-toggle"
          :class="{ active: pendingOnly }"
          type="button"
          :aria-pressed="pendingOnly"
          @click="emit('update:pendingOnly', !pendingOnly)"
        >
          <Filter :size="14" />
          仅看待复验
          <span v-if="pendingOnly">{{ filteredChunks.length }}</span>
        </button>
      </div>

      <div class="chunk-list-heading">
        <span>Chunk 列表</span>
        <strong>{{ filteredChunks.length }}</strong>
      </div>

      <div class="chunk-list" aria-label="Chunk 列表">
        <button
          v-for="chunk in filteredChunks"
          :key="chunk.chunk_id"
          class="chunk-row"
          :class="{
            active: chunk.chunk_id === activeChunkId,
            approved: chunk.approved,
            modified: chunk.has_changes,
            issue: chunk.issue_count,
          }"
          type="button"
          @click="emit('selectChunk', chunk.chunk_id)"
        >
          <span class="chunk-index">{{ String(chunk.index).padStart(2, "0") }}</span>
          <span class="chunk-row-content">
            <span class="chunk-row-title">{{ chunk.section_title }}</span>
            <span class="chunk-row-meta">
              <span>P{{ chunk.page_start || "—" }}</span>
              <span>{{ chunk.entity_count }} 实体</span>
              <span>{{ chunk.relation_count }} 关系</span>
            </span>
            <span class="chunk-status">
              <AlertCircle v-if="chunk.issue_count" :size="13" />
              <CheckCircle2 v-else-if="chunk.approved" :size="13" />
              <PencilLine v-else-if="chunk.has_changes" :size="13" />
              <Clock3 v-else :size="13" />
              {{ statusLabel(chunk) }}
            </span>
          </span>
          <ChevronRight :size="15" class="chunk-arrow" />
        </button>

        <div v-if="!filteredChunks.length" class="list-empty">
          <Filter :size="20" />
          <strong>没有符合条件的 Chunk</strong>
          <button type="button" @click="emit('clearFilters')">清除筛选</button>
        </div>
      </div>
    </template>

    <button
      v-else
      class="collapsed-rail-button"
      type="button"
      aria-label="展开 Chunk 导航"
      @click="emit('update:collapsed', false)"
    >
      <PanelLeftOpen :size="19" />
      <span>CHUNK</span>
    </button>
  </aside>
</template>

<style scoped>
.chunk-sidebar {
  position: relative;
  z-index: 8;
  display: flex;
  width: 284px;
  min-width: 0;
  flex: 0 0 auto;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: rgba(250, 252, 255, 0.9);
  backdrop-filter: blur(18px);
  transition: width var(--ease);
}

.chunk-sidebar.collapsed {
  width: 48px;
}

.sidebar-overview {
  padding: 17px 15px 14px;
  border-bottom: 1px solid var(--border);
}

.overview-head,
.overview-head > div,
.overview-meta {
  display: flex;
  align-items: center;
}

.overview-head {
  justify-content: space-between;
  margin-bottom: 12px;
}

.overview-head > div {
  align-items: baseline;
  gap: 8px;
}

.overview-head strong {
  color: #2e3850;
  font-size: 18px;
  font-variant-numeric: tabular-nums;
}

.progress-track {
  height: 6px;
  overflow: hidden;
  border-radius: 99px;
  background: #e8edf4;
}

.progress-value {
  height: 100%;
  border-radius: inherit;
  background: var(--primary);
  transition: width 350ms ease;
}

.overview-meta {
  justify-content: space-between;
  margin-top: 9px;
  color: var(--text-faint);
  font-size: 11px;
}

.overview-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.overview-meta .issue-text {
  color: var(--amber);
}

.document-picker {
  padding: 13px 12px 10px;
  border-bottom: 1px solid rgba(225, 231, 240, 0.75);
}

.document-picker > .eyebrow {
  display: block;
  margin: 0 3px 7px;
}

.document-select {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr) 16px;
  align-items: center;
  gap: 7px;
  padding: 9px 9px;
  color: var(--primary);
  border: 1px solid #dce0f7;
  border-radius: 11px;
  background: #f7f7ff;
}

.document-select > span {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.document-select select {
  width: 100%;
  min-width: 0;
  padding: 0 20px 0 0;
  overflow: hidden;
  color: #354057;
  border: 0;
  outline: 0;
  appearance: none;
  background: transparent;
  font-size: 12px;
  font-weight: 680;
  text-overflow: ellipsis;
}

.document-select small {
  color: var(--text-faint);
  font-size: 10px;
}

.chunk-tools {
  display: grid;
  gap: 8px;
  padding: 11px 12px 9px;
}

.search-field {
  display: flex;
  height: 35px;
  align-items: center;
  gap: 7px;
  padding: 0 10px;
  color: var(--text-faint);
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.8);
}

.search-field:focus-within {
  color: var(--primary);
  border-color: #c9cef6;
  box-shadow: 0 0 0 3px rgba(89, 100, 223, 0.09);
}

.search-field input {
  width: 100%;
  min-width: 0;
  padding: 0;
  border: 0;
  outline: 0;
  background: transparent;
  font-size: 12px;
}

.filter-toggle {
  display: flex;
  width: fit-content;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  cursor: pointer;
  color: var(--text-faint);
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  font-size: 11px;
  font-weight: 600;
}

.filter-toggle:hover,
.filter-toggle.active {
  color: var(--primary);
  border-color: #dce0fb;
  background: var(--primary-soft);
}

.filter-toggle span {
  padding: 1px 5px;
  border-radius: 99px;
  background: #fff;
  font-size: 9px;
}

.chunk-list-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 7px 14px 5px;
  color: var(--text-faint);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.chunk-list-heading strong {
  font-size: 10px;
}

.chunk-list {
  min-height: 0;
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 2px 9px 18px;
  scrollbar-color: #cfd7e4 transparent;
  scrollbar-width: thin;
}

.chunk-row {
  position: relative;
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) 14px;
  width: 100%;
  gap: 7px;
  margin: 2px 0;
  padding: 11px 8px;
  cursor: pointer;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 11px;
  background: transparent;
}

.chunk-row:hover {
  border-color: #e5e9f2;
  background: rgba(255, 255, 255, 0.76);
}

.chunk-row.active {
  border-color: #d9ddfb;
  background: #f0f2ff;
}

.chunk-row.active::before {
  position: absolute;
  top: 12px;
  bottom: 12px;
  left: -9px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--primary);
  content: "";
}

.chunk-index {
  padding-top: 1px;
  color: #9aa4b5;
  font-size: 10px;
  font-weight: 760;
}

.chunk-row.active .chunk-index {
  color: var(--primary);
}

.chunk-row-content {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}

.chunk-row-title {
  overflow: hidden;
  color: #354057;
  font-size: 12px;
  font-weight: 680;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chunk-row-meta,
.chunk-status {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--text-faint);
  font-size: 10px;
}

.chunk-status {
  gap: 4px;
  font-weight: 620;
}

.chunk-row.approved .chunk-status {
  color: var(--teal);
}

.chunk-row.modified .chunk-status {
  color: var(--primary);
}

.chunk-row.issue .chunk-status {
  color: var(--amber);
}

.chunk-arrow {
  align-self: center;
  color: #a8b1c0;
  opacity: 0;
}

.chunk-row:hover .chunk-arrow,
.chunk-row.active .chunk-arrow {
  opacity: 1;
}

.list-empty {
  display: flex;
  min-height: 220px;
  align-items: center;
  flex-direction: column;
  justify-content: center;
  gap: 7px;
  color: var(--text-faint);
  text-align: center;
  font-size: 11px;
}

.list-empty strong {
  color: var(--text-soft);
  font-size: 12px;
}

.list-empty button {
  cursor: pointer;
  color: var(--primary);
  background: transparent;
}

.collapsed-rail-button {
  display: flex;
  width: 100%;
  height: 100%;
  align-items: center;
  gap: 14px;
  padding-top: 16px;
  cursor: pointer;
  color: var(--text-faint);
  flex-direction: column;
  background: transparent;
}

.collapsed-rail-button:hover {
  color: var(--primary);
  background: rgba(238, 240, 255, 0.7);
}

.collapsed-rail-button span {
  font-size: 9px;
  font-weight: 750;
  letter-spacing: 0.12em;
  writing-mode: vertical-rl;
}

@media (max-width: 1279px) {
  .chunk-sidebar {
    width: 252px;
  }
}

@media (max-width: 1100px) {
  .chunk-sidebar {
    width: 220px;
  }

  .sidebar-overview,
  .document-picker {
    padding-right: 10px;
    padding-left: 10px;
  }

  .overview-meta {
    font-size: 9px;
  }
}
</style>
