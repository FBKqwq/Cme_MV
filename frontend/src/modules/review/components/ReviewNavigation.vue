<script setup lang="ts">
import {
  AlertCircle,
  CheckCircle2,
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
  const values = new Map<
    string,
    { total: number; approved: number; issues: number; modified: number }
  >();
  for (const chunk of props.chunks) {
    const title = chunk._source_title || "未命名文档";
    const stats = values.get(title) || {
      total: 0,
      approved: 0,
      issues: 0,
      modified: 0,
    };
    stats.total += 1;
    if (chunk.approved) stats.approved += 1;
    stats.issues += chunk.issue_count;
    if (chunk.has_changes) stats.modified += 1;
    values.set(title, stats);
  }
  const order = new Map(
    (props.task?.documents ?? []).map((document, index) => [
      document.title,
      index,
    ]),
  );
  return Array.from(values, ([title, stats]) => ({ title, ...stats })).sort(
    (a, b) =>
      (order.get(a.title) ?? Number.MAX_SAFE_INTEGER) -
        (order.get(b.title) ?? Number.MAX_SAFE_INTEGER) ||
      a.title.localeCompare(b.title, "zh-CN"),
  );
});

const currentDocumentTitle = computed(
  () =>
    props.selectedPdf ||
    props.chunks.find((chunk) => chunk.chunk_id === props.activeChunkId)
      ?._source_title ||
    documentOptions.value[0]?.title ||
    "",
);

const visibleChunks = computed(() =>
  props.filteredChunks.filter(
    (chunk) =>
      (chunk._source_title || "未命名文档") === currentDocumentTitle.value,
  ),
);
</script>

<template>
  <aside class="chunk-sidebar" :class="{ collapsed }">
    <template v-if="!collapsed">
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
          :aria-label="pendingOnly ? '显示全部 Chunk' : '仅看待复验'"
          :aria-pressed="pendingOnly"
          :title="pendingOnly ? '显示全部 Chunk' : '仅看待复验'"
          @click="emit('update:pendingOnly', !pendingOnly)"
        >
          <Filter :size="16" />
          <span v-if="pendingOnly" class="filter-count">{{ filteredChunks.length }}</span>
        </button>
        <button
          class="toolbar-icon-button"
          type="button"
          aria-label="折叠 Chunk 导航"
          title="折叠导航"
          @click="emit('update:collapsed', true)"
        >
          <PanelLeftClose :size="17" />
        </button>
      </div>

      <div class="navigation-section-heading">
        <span>PDF 文档</span>
        <strong>{{ documentOptions.length }}</strong>
      </div>

      <div class="document-list" aria-label="PDF 文档列表">
        <button
          v-for="document in documentOptions"
          :key="document.title"
          class="document-row"
          :class="{ active: document.title === currentDocumentTitle }"
          type="button"
          @click="emit('update:selectedPdf', document.title)"
        >
          <span class="document-icon"><FileText :size="16" /></span>
          <span class="document-row-content">
            <span class="document-row-title">
              {{ document.title.replace(/\u300a|\u300b/g, "") }}
            </span>
            <span class="document-row-meta">
              {{ document.total }} Chunks
              <span aria-hidden="true">·</span>
              {{ document.approved }}/{{ document.total }} 已通过
            </span>
          </span>
          <span v-if="document.issues" class="document-issue">
            {{ document.issues }}
          </span>
          <CheckCircle2
            v-else-if="document.approved === document.total"
            :size="15"
            class="document-complete"
          />
          <ChevronRight v-else :size="15" class="document-arrow" />
        </button>
      </div>

      <div class="navigation-section-heading chunk-heading">
        <span>Chunk 列表</span>
        <strong>{{ visibleChunks.length }}</strong>
      </div>

      <div class="chunk-list" aria-label="Chunk 列表">
        <button
          v-for="chunk in visibleChunks"
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

        <div v-if="!visibleChunks.length" class="list-empty">
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
  width: 300px;
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

.chunk-tools {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-bottom: 1px solid rgba(225, 231, 240, 0.75);
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
  position: relative;
  display: flex;
  width: 36px;
  height: 36px;
  align-items: center;
  justify-content: center;
  padding: 0;
  cursor: pointer;
  color: var(--text-faint);
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.8);
}

.filter-toggle:hover,
.filter-toggle.active {
  color: var(--primary);
  border-color: #dce0fb;
  background: var(--primary-soft);
}

.filter-toggle .filter-count {
  position: absolute;
  top: -5px;
  right: -5px;
  min-width: 16px;
  padding: 1px 4px;
  color: #fff;
  border-radius: 99px;
  background: var(--primary);
  box-shadow: 0 0 0 2px #fafdff;
  font-size: 8px;
  font-weight: 750;
  line-height: 14px;
  text-align: center;
}

.toolbar-icon-button {
  display: grid;
  width: 36px;
  height: 36px;
  cursor: pointer;
  place-items: center;
  color: var(--text-faint);
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
}

.toolbar-icon-button:hover {
  color: var(--primary);
  border-color: #dce0fb;
  background: var(--primary-soft);
}

.navigation-section-heading {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  padding: 9px 13px 7px;
  color: var(--text-faint);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.navigation-section-heading strong {
  font-size: 10px;
}

.document-list {
  max-height: 36%;
  min-height: 112px;
  overflow-x: hidden;
  overflow-y: auto;
  border-bottom: 1px solid var(--border);
  scrollbar-color: #cfd7e4 transparent;
  scrollbar-width: thin;
}

.document-row {
  position: relative;
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) 20px;
  width: 100%;
  align-items: center;
  gap: 8px;
  padding: 10px 11px 10px 12px;
  cursor: pointer;
  text-align: left;
  color: inherit;
  border: 0;
  border-bottom: 1px solid #edf0f5;
  background: transparent;
}

.document-row:hover {
  background: rgba(255, 255, 255, 0.78);
}

.document-row.active {
  background: #f0f2ff;
}

.document-row.active::before {
  position: absolute;
  inset: 8px auto 8px 0;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--primary);
  content: "";
}

.document-icon {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  color: #78849a;
  border: 1px solid #e3e7ef;
  border-radius: 8px;
  background: #fff;
}

.document-row.active .document-icon {
  color: var(--primary);
  border-color: #d9ddfb;
}

.document-row-content {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.document-row-title {
  overflow: hidden;
  color: #354057;
  font-size: 12px;
  font-weight: 680;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-row-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-faint);
  font-size: 10px;
}

.document-issue {
  min-width: 19px;
  padding: 2px 5px;
  color: #b66a09;
  border-radius: 99px;
  background: #fff3d9;
  font-size: 9px;
  font-weight: 750;
  text-align: center;
}

.document-complete {
  color: var(--teal);
}

.document-arrow {
  color: #a8b1c0;
}

.chunk-heading {
  border-bottom: 1px solid rgba(225, 231, 240, 0.65);
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

}
</style>
