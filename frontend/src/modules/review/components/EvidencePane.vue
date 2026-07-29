<script setup lang="ts">
import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  FileText,
  Highlighter,
  LoaderCircle,
  Plus,
} from "lucide-vue-next";
import type { ChunkDetail, ChunkSummary, EntityRecord } from "../types";

defineProps<{
  detail: ChunkDetail | null;
  detailLoading: boolean;
  currentSummary?: ChunkSummary;
  highlightedSegments: Array<{ text: string; entity?: EntityRecord }>;
  selectedEntityId: string;
  selectedEvidence: string;
  selectedEvidencePosition: { x: number; y: number };
  currentPdfAvailable: boolean;
  currentPage: number;
  activeChunkIndex: number;
  totalChunks: number;
}>();

const emit = defineEmits<{
  openPdf: [];
  relative: [offset: -1 | 1];
  selectEntity: [entity: EntityRecord];
  captureSelection: [event: MouseEvent];
  createFromSelection: [];
  approveNext: [];
}>();
</script>

<template>
  <section class="evidence-workspace">
    <div v-if="detailLoading" class="reader-loading">
      <LoaderCircle :size="24" class="spin" />
      正在切换证据…
    </div>

    <template v-else-if="detail">
      <div class="evidence-toolbar">
        <div class="chunk-heading">
          <span class="chunk-kicker">
            Chunk {{ String(currentSummary?.index || 0).padStart(2, "0") }}
            <span aria-hidden="true">·</span>
            {{ detail.chunk.chunk_id }}
          </span>
          <h1>{{ detail.chunk.section_title || "未命名章节" }}</h1>
          <div v-if="detail.chunk.section_path?.length" class="breadcrumb">
            <template
              v-for="(section, index) in detail.chunk.section_path"
              :key="`${section}-${index}`"
            >
              <span>{{ section }}</span>
              <ChevronRight
                v-if="index < detail.chunk.section_path.length - 1"
                :size="12"
              />
            </template>
          </div>
        </div>

        <div class="reader-actions">
          <button
            class="page-link"
            type="button"
            :disabled="!currentPdfAvailable"
            @click="emit('openPdf')"
          >
            <FileText :size="15" />
            PDF 第 {{ currentPage }} 页
            <ExternalLink :size="13" />
          </button>
          <button
            class="icon-button subtle"
            type="button"
            :disabled="activeChunkIndex <= 0"
            aria-label="上一个 Chunk"
            @click="emit('relative', -1)"
          >
            <ChevronLeft :size="18" />
          </button>
          <button
            class="icon-button subtle"
            type="button"
            :disabled="activeChunkIndex >= totalChunks - 1"
            aria-label="下一个 Chunk"
            @click="emit('relative', 1)"
          >
            <ChevronRight :size="18" />
          </button>
        </div>
      </div>

      <div class="evidence-context">
        <span><Highlighter :size="14" />点击高亮可定位抽取结果</span>
        <span>选中文字可快速新建实体</span>
      </div>

      <article class="evidence-reader" @mouseup="emit('captureSelection', $event)">
        <p class="evidence-text">
          <template
            v-for="(segment, index) in highlightedSegments"
            :key="`${index}-${segment.text.slice(0, 12)}`"
          >
            <button
              v-if="segment.entity"
              class="entity-highlight"
              :class="[
                `type-${segment.entity.entity_type}`,
                {
                  active: selectedEntityId === segment.entity.entity_id,
                  modified: segment.entity._review.modified,
                },
              ]"
              type="button"
              @click.stop="emit('selectEntity', segment.entity)"
            >
              {{ segment.text }}
              <span class="highlight-dot" aria-hidden="true"></span>
            </button>
            <span v-else>{{ segment.text }}</span>
          </template>
        </p>
      </article>

      <button
        v-if="selectedEvidence"
        class="selection-action"
        type="button"
        :style="{
          left: `${selectedEvidencePosition.x}px`,
          top: `${selectedEvidencePosition.y}px`,
        }"
        @mousedown.prevent
        @click="emit('createFromSelection')"
      >
        <Plus :size="15" />
        新建实体
      </button>

      <footer class="review-actionbar">
        <div class="actionbar-status">
          <span
            class="status-orb"
            :class="{
              approved: detail.review.status === 'approved',
              issue: detail.review.issue_count > 0,
            }"
          >
            <AlertCircle v-if="detail.review.issue_count" :size="15" />
            <Check v-else-if="detail.review.status === 'approved'" :size="15" />
            <CheckCircle2 v-else :size="15" />
          </span>
          <div>
            <strong v-if="detail.review.issue_count">
              {{ detail.review.issue_count }} 项阻塞问题
            </strong>
            <strong v-else-if="detail.review.status === 'approved'">当前 Chunk 已通过</strong>
            <strong v-else>当前 Chunk 待复验</strong>
            <span>
              {{ detail.entities.length }} 个实体 ·
              {{ detail.relationships.length }} 条关系
            </span>
          </div>
        </div>
        <div class="actionbar-actions">
          <button
            class="button quiet"
            type="button"
            :disabled="activeChunkIndex >= totalChunks - 1"
            @click="emit('relative', 1)"
          >
            暂存并跳过
          </button>
          <button class="button approve" type="button" @click="emit('approveNext')">
            <CheckCircle2 :size="17" />
            通过并进入下一 Chunk
            <ArrowRight :size="16" />
          </button>
        </div>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.evidence-workspace {
  position: relative;
  display: flex;
  min-width: 420px;
  flex: 1 1 auto;
  flex-direction: column;
  overflow: hidden;
  background: #f5f7fb;
}

.reader-loading {
  display: flex;
  height: 100%;
  align-items: center;
  justify-content: center;
  gap: 9px;
  color: var(--text-faint);
  font-size: 13px;
}

.evidence-toolbar {
  display: flex;
  min-height: 82px;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 14px 24px 11px;
  border-bottom: 1px solid var(--border);
  background: rgba(252, 253, 255, 0.88);
}

.chunk-heading {
  min-width: 0;
}

.chunk-kicker {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 5px;
  color: var(--primary);
  font-size: 10px;
  font-weight: 740;
  letter-spacing: 0.055em;
  text-transform: uppercase;
}

.chunk-heading h1 {
  overflow: hidden;
  max-width: 720px;
  margin: 0;
  color: #222c41;
  font-size: 19px;
  font-weight: 720;
  letter-spacing: -0.025em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.breadcrumb {
  display: flex;
  max-width: 720px;
  align-items: center;
  gap: 2px;
  margin-top: 5px;
  overflow: hidden;
  color: var(--text-faint);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reader-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 5px;
}

.page-link {
  display: flex;
  min-height: 34px;
  align-items: center;
  gap: 6px;
  margin-right: 3px;
  padding: 0 10px;
  cursor: pointer;
  color: var(--primary);
  border: 1px solid #dce0f7;
  border-radius: 9px;
  background: #f7f7ff;
  font-size: 11px;
  font-weight: 640;
}

.evidence-context {
  display: flex;
  min-height: 34px;
  align-items: center;
  justify-content: space-between;
  padding: 0 25px;
  color: var(--text-faint);
  border-bottom: 1px solid rgba(225, 231, 240, 0.75);
  background: rgba(247, 249, 252, 0.72);
  font-size: 10px;
}

.evidence-context span {
  display: flex;
  align-items: center;
  gap: 5px;
}

.evidence-reader {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  padding: 34px clamp(34px, 5vw, 72px) calc(var(--actionbar-height) + 34px);
  scrollbar-color: #cbd4e2 transparent;
  scrollbar-width: thin;
}

.evidence-text {
  max-width: 900px;
  margin: 0 auto;
  color: #303a4c;
  font-family: "Noto Serif SC", "Songti SC", SimSun, serif;
  font-size: 16px;
  font-weight: 420;
  line-height: 2.04;
  letter-spacing: 0.016em;
  white-space: pre-wrap;
  word-break: break-word;
}

.entity-highlight {
  position: relative;
  display: inline;
  margin: 0 1px;
  padding: 2px;
  cursor: pointer;
  color: inherit;
  border-radius: 4px;
  background: rgba(105, 116, 226, 0.13);
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
  font-family: inherit;
  font-size: inherit;
  line-height: inherit;
  text-align: left;
}

.entity-highlight:hover,
.entity-highlight.active {
  color: #2734a7;
  background: rgba(89, 100, 223, 0.2);
  box-shadow: 0 0 0 2px rgba(89, 100, 223, 0.13);
}

.entity-highlight.modified,
.entity-highlight.type-treatments,
.entity-highlight.type-plans {
  background: rgba(21, 159, 145, 0.14);
}

.entity-highlight.type-symptoms,
.entity-highlight.type-sub_diseases {
  background: rgba(78, 132, 214, 0.13);
}

.entity-highlight.type-tests {
  background: rgba(181, 121, 38, 0.14);
}

.entity-highlight.type-etiologies,
.entity-highlight.type-pathogeneses {
  background: rgba(156, 98, 190, 0.14);
}

.highlight-dot {
  display: inline-block;
  width: 4px;
  height: 4px;
  margin: 0 1px 2px 2px;
  border-radius: 99px;
  background: var(--primary);
}

.selection-action {
  position: fixed;
  z-index: 45;
  display: flex;
  min-height: 34px;
  align-items: center;
  gap: 6px;
  padding: 0 11px;
  cursor: pointer;
  color: #fff;
  border-radius: 9px;
  background: #29344b;
  box-shadow: var(--shadow-md);
  font-size: 12px;
  font-weight: 650;
}

.review-actionbar {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 7;
  display: flex;
  height: var(--actionbar-height);
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 0 22px;
  border-top: 1px solid var(--border);
  background: rgba(250, 252, 255, 0.93);
  box-shadow: 0 -10px 32px rgba(38, 50, 81, 0.055);
  backdrop-filter: blur(16px);
}

.actionbar-status,
.actionbar-actions {
  display: flex;
  align-items: center;
}

.actionbar-status {
  min-width: 0;
  gap: 10px;
}

.actionbar-status > div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.actionbar-status strong {
  overflow: hidden;
  color: #354057;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actionbar-status span {
  color: var(--text-faint);
  font-size: 10px;
}

.status-orb {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  place-items: center;
  color: var(--text-faint);
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-muted);
}

.status-orb.approved {
  color: var(--teal);
  border-color: #ccebe6;
  background: var(--teal-soft);
}

.status-orb.issue {
  color: var(--amber);
  border-color: #f0dcb7;
  background: var(--amber-soft);
}

.actionbar-actions {
  gap: 8px;
}

@media (max-height: 820px) {
  .evidence-toolbar {
    min-height: 74px;
    padding-top: 10px;
    padding-bottom: 8px;
  }

  .evidence-reader {
    padding-top: 25px;
  }

  .evidence-text {
    font-size: 15px;
    line-height: 1.92;
  }
}

@media (max-width: 1100px) {
  .evidence-toolbar {
    gap: 12px;
    padding-right: 14px;
    padding-left: 18px;
  }

  .chunk-heading h1 {
    max-width: 260px;
    font-size: 17px;
  }

  .evidence-reader {
    padding-right: 28px;
    padding-left: 28px;
  }

  .review-actionbar {
    padding: 0 12px;
  }

  .actionbar-status > div > span {
    display: none;
  }

  .actionbar-actions .button.quiet {
    display: none;
  }
}
</style>
