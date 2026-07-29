<script setup lang="ts">
import {
  BookOpenText,
  ChevronDown,
  GitBranch,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  ShieldCheck,
} from "lucide-vue-next";
import type { ChunkDetail, ReviewTab, TaskInfo } from "../types";

defineProps<{
  detail: ChunkDetail | null;
  task: TaskInfo | null;
  activeTab: ReviewTab;
  collapsed: boolean;
  width: number;
}>();

const emit = defineEmits<{
  "update:activeTab": [tab: ReviewTab];
  "update:collapsed": [collapsed: boolean];
  add: [];
}>();
</script>

<template>
  <aside
    class="review-inspector"
    :class="{ collapsed }"
    :style="collapsed ? undefined : { width: `${width}px` }"
  >
    <template v-if="!collapsed && detail">
      <div class="inspector-head">
        <div class="tab-list" role="tablist" aria-label="复验结果类型">
          <button
            class="review-tab"
            :class="{ active: activeTab === 'entities' }"
            type="button"
            role="tab"
            :aria-selected="activeTab === 'entities'"
            @click="emit('update:activeTab', 'entities')"
          >
            <BookOpenText :size="16" />
            实体
            <span>{{ detail.entities.length }}</span>
          </button>
          <button
            class="review-tab"
            :class="{ active: activeTab === 'relationships' }"
            type="button"
            role="tab"
            :aria-selected="activeTab === 'relationships'"
            @click="emit('update:activeTab', 'relationships')"
          >
            <GitBranch :size="16" />
            关系
            <span>{{ detail.relationships.length }}</span>
            <i v-if="detail.review.issue_count">{{ detail.review.issue_count }}</i>
          </button>
        </div>
        <button
          class="icon-button subtle"
          type="button"
          aria-label="折叠复验编辑器"
          @click="emit('update:collapsed', true)"
        >
          <PanelRightClose :size="18" />
        </button>
      </div>

      <div class="inspector-summary">
        <div>
          <span class="eyebrow">
            {{ activeTab === "entities" ? "实体复验" : "关系复验" }}
          </span>
          <p>
            {{
              activeTab === "entities"
                ? "逐项确认抽取实体，修改仅作用于当前提及。"
                : "核对关系端点与类型，冲突项必须先处理。"
            }}
          </p>
        </div>
        <button class="button compact" type="button" @click="emit('add')">
          <Plus :size="15" />
          新增{{ activeTab === "entities" ? "实体" : "关系" }}
        </button>
      </div>

      <slot></slot>

      <details class="debug-details">
        <summary>
          <span><ShieldCheck :size="14" />溯源与调试信息</span>
          <ChevronDown :size="15" />
        </summary>
        <dl>
          <div><dt>Chunk ID</dt><dd>{{ detail.chunk.chunk_id }}</dd></div>
          <div><dt>修订版本</dt><dd>v{{ detail.version }}</dd></div>
          <div><dt>Schema</dt><dd>V{{ task?.document.schema_version }}</dd></div>
          <div><dt>输入哈希</dt><dd>{{ task?.input_hash.slice(0, 12) }}…</dd></div>
        </dl>
      </details>
    </template>

    <button
      v-else
      class="collapsed-rail-button right"
      type="button"
      aria-label="展开复验编辑器"
      @click="emit('update:collapsed', false)"
    >
      <PanelRightOpen :size="19" />
      <span>复验</span>
    </button>
  </aside>
</template>

<style scoped>
.review-inspector {
  position: relative;
  z-index: 8;
  display: flex;
  width: 430px;
  min-width: 0;
  max-width: 620px;
  flex: 0 0 auto;
  flex-direction: column;
  border-left: 1px solid var(--border);
  background: rgba(251, 252, 255, 0.96);
  transition: width var(--ease);
}

.review-inspector.collapsed {
  width: 48px;
}

.inspector-head {
  display: flex;
  min-height: 56px;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 11px 7px 15px;
  border-bottom: 1px solid var(--border);
}

.tab-list {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 3px;
  border-radius: 10px;
  background: #eff2f7;
}

.review-tab {
  position: relative;
  display: flex;
  min-height: 34px;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  cursor: pointer;
  color: #748094;
  border-radius: 8px;
  background: transparent;
  font-size: 12px;
  font-weight: 650;
}

.review-tab > span {
  min-width: 19px;
  padding: 2px 5px;
  border-radius: 99px;
  background: rgba(140, 151, 169, 0.12);
  font-size: 9px;
  text-align: center;
}

.review-tab > i {
  position: absolute;
  top: -4px;
  right: -4px;
  display: grid;
  min-width: 16px;
  height: 16px;
  place-items: center;
  color: #fff;
  border: 2px solid #fff;
  border-radius: 99px;
  background: var(--amber);
  font-size: 8px;
  font-style: normal;
}

.review-tab.active {
  color: var(--primary);
  background: #fff;
  box-shadow: 0 2px 8px rgba(37, 49, 81, 0.08);
}

.review-tab.active > span {
  color: var(--primary);
  background: var(--primary-soft);
}

.inspector-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 14px;
  border-bottom: 1px solid rgba(225, 231, 240, 0.75);
  background: rgba(247, 249, 252, 0.72);
}

.inspector-summary > div {
  min-width: 0;
}

.inspector-summary p {
  overflow: hidden;
  margin: 4px 0 0;
  color: var(--text-soft);
  font-size: 10px;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.debug-details {
  flex: 0 0 auto;
  border-top: 1px solid var(--border);
  background: rgba(247, 249, 252, 0.9);
}

.debug-details summary {
  display: flex;
  min-height: 38px;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  cursor: pointer;
  color: var(--text-faint);
  font-size: 10px;
  font-weight: 650;
  list-style: none;
}

.debug-details summary span {
  display: flex;
  align-items: center;
  gap: 6px;
}

.debug-details dl {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 7px 12px;
  margin: 0;
  padding: 0 14px 12px;
  font-size: 9px;
}

.debug-details dl div {
  min-width: 0;
}

.debug-details dt {
  color: var(--text-faint);
}

.debug-details dd {
  overflow: hidden;
  margin: 2px 0 0;
  color: var(--text-soft);
  text-overflow: ellipsis;
  white-space: nowrap;
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
  .review-inspector {
    width: 380px !important;
  }
}

@media (max-width: 1100px) {
  .review-inspector {
    width: 340px !important;
  }

  .inspector-summary p {
    max-width: 185px;
  }
}
</style>
