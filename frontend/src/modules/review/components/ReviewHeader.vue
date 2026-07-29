<script setup lang="ts">
import {
  ArrowLeftToLine,
  CheckCircle2,
  ChevronDown,
  Circle,
  Download,
  FileCheck2,
  LoaderCircle,
  MoreHorizontal,
  ShieldCheck,
  Upload,
  AlertCircle,
} from "lucide-vue-next";
import type { SaveState, TaskInfo } from "../types";

defineProps<{
  task: TaskInfo | null;
  saveState: SaveState;
  savingLabel: string;
}>();

const emit = defineEmits<{
  back: [];
  import: [event: Event];
  export: [];
  finalize: [];
}>();
</script>

<template>
  <header class="topbar">
    <div class="brand-block">
      <div class="brand-mark" aria-hidden="true">
        <ShieldCheck :size="21" :stroke-width="1.9" />
      </div>
      <div class="brand-copy">
        <div class="brand-name">医师复验工作台</div>
        <div class="brand-context">
          <span class="live-dot" aria-hidden="true"></span>
          证据抽取复核
        </div>
      </div>
    </div>

    <div v-if="task" class="document-heading">
      <div class="document-heading-main">
        <span class="document-title">{{ task.document.title }}</span>
        <span class="contract-badge">Graph Contract V{{ task.document.schema_version }}</span>
      </div>
      <div class="header-progress" aria-label="全篇复验进度">
        <span class="header-progress-label">
          复验进度
          <strong>{{ task.progress.approved }}/{{ task.progress.total }}</strong>
        </span>
        <span class="header-progress-track">
          <span
            class="header-progress-value"
            :style="{ width: `${task.progress.percent}%` }"
          ></span>
        </span>
        <span class="header-progress-percent">{{ task.progress.percent }}%</span>
        <span v-if="task.progress.issues" class="header-progress-issues">
          <AlertCircle :size="12" />{{ task.progress.issues }} 项需处理
        </span>
        <span v-else class="header-progress-clear">
          <CheckCircle2 :size="12" />暂无阻塞
        </span>
      </div>
    </div>

    <div class="topbar-actions">
      <div class="save-indicator" :class="saveState" role="status">
        <LoaderCircle v-if="saveState === 'saving'" :size="14" class="spin" />
        <CheckCircle2 v-else-if="saveState === 'saved'" :size="14" />
        <AlertCircle v-else-if="saveState === 'error'" :size="14" />
        <Circle v-else :size="10" />
        <span>{{ savingLabel }}</span>
      </div>

      <details class="utility-menu">
        <summary class="button quiet" aria-label="更多复验操作">
          <MoreHorizontal :size="17" />
          <span>更多</span>
          <ChevronDown :size="14" />
        </summary>
        <div class="utility-menu-popover">
          <button type="button" @click="emit('back')">
            <ArrowLeftToLine :size="16" />
            <span><strong>返回诊断系统</strong><small>离开复验工作台</small></span>
          </button>
          <label>
            <Upload :size="16" />
            <span><strong>导入复验</strong><small>载入 ZIP 复验包</small></span>
            <input type="file" accept=".zip" @change="emit('import', $event)" />
          </label>
          <button type="button" @click="emit('export')">
            <Download :size="16" />
            <span><strong>导出草稿</strong><small>保存当前复验进度</small></span>
          </button>
        </div>
      </details>

      <button class="button primary finalize-button" type="button" @click="emit('finalize')">
        <FileCheck2 :size="16" />
        完成本篇复验
      </button>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  position: relative;
  z-index: 30;
  display: grid;
  grid-template-columns: minmax(220px, 0.75fr) minmax(280px, 1.35fr) minmax(340px, 0.9fr);
  align-items: center;
  height: var(--topbar-height);
  padding: 0 18px;
  border-bottom: 1px solid rgba(218, 225, 236, 0.9);
  background: rgba(250, 252, 255, 0.92);
  box-shadow: 0 2px 18px rgba(35, 47, 78, 0.04);
  backdrop-filter: blur(18px);
}

.brand-block,
.topbar-actions,
.document-heading-main,
.header-progress,
.header-progress-label,
.header-progress-issues,
.header-progress-clear,
.save-indicator {
  display: flex;
  align-items: center;
}

.brand-block {
  min-width: 0;
  gap: 11px;
}

.brand-mark {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  place-items: center;
  color: #fff;
  border-radius: 12px;
  background: var(--primary);
  box-shadow: 0 7px 16px rgba(89, 100, 223, 0.22);
}

.brand-copy {
  min-width: 0;
}

.brand-name {
  overflow: hidden;
  color: #212a3d;
  font-size: 15px;
  font-weight: 720;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.brand-context {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
  color: var(--text-faint);
  font-size: 11px;
  font-weight: 560;
}

.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 99px;
  background: var(--teal);
  box-shadow: 0 0 0 3px rgba(21, 159, 145, 0.11);
}

.document-heading {
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
  gap: 5px;
  padding: 0 18px;
}

.document-heading-main {
  min-width: 0;
  justify-content: center;
  gap: 10px;
}

.document-title {
  overflow: hidden;
  max-width: 460px;
  color: #303a50;
  font-size: 14px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.contract-badge {
  flex: 0 0 auto;
  padding: 4px 8px;
  color: #6672c9;
  border: 1px solid #dce0ff;
  border-radius: 99px;
  background: #f5f6ff;
  font-size: 10px;
  font-weight: 700;
}

.header-progress {
  width: min(100%, 520px);
  justify-content: center;
  gap: 8px;
  color: var(--text-faint);
  font-size: 10px;
  white-space: nowrap;
}

.header-progress-label {
  gap: 5px;
}

.header-progress-label strong {
  color: #344057;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.header-progress-track {
  position: relative;
  width: clamp(78px, 14vw, 180px);
  height: 5px;
  overflow: hidden;
  border-radius: 99px;
  background: #e4e9f1;
}

.header-progress-value {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: inherit;
  background: var(--primary);
  transition: width 350ms ease;
}

.header-progress-percent {
  min-width: 27px;
  font-variant-numeric: tabular-nums;
}

.header-progress-issues,
.header-progress-clear {
  gap: 3px;
}

.header-progress-issues {
  color: var(--amber);
}

.header-progress-clear {
  color: var(--teal);
}

.topbar-actions {
  justify-content: flex-end;
  gap: 8px;
}

.save-indicator {
  gap: 6px;
  color: var(--text-faint);
  font-size: 12px;
  white-space: nowrap;
}

.save-indicator.saved,
.save-indicator.saving {
  color: var(--teal);
}

.save-indicator.dirty {
  color: var(--amber);
}

.save-indicator.error {
  color: var(--red);
}

.utility-menu {
  position: relative;
}

.utility-menu summary {
  list-style: none;
}

.utility-menu summary::-webkit-details-marker {
  display: none;
}

.utility-menu[open] summary {
  color: var(--primary);
  border-color: #cfd5f6;
  background: var(--primary-soft);
}

.utility-menu-popover {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 50;
  width: 230px;
  padding: 7px;
  border: 1px solid var(--border);
  border-radius: 13px;
  background: #fff;
  box-shadow: var(--shadow-md);
}

.utility-menu-popover button,
.utility-menu-popover label {
  position: relative;
  display: flex;
  width: 100%;
  align-items: center;
  gap: 10px;
  padding: 10px;
  cursor: pointer;
  text-align: left;
  border-radius: 9px;
  background: transparent;
}

.utility-menu-popover button:hover,
.utility-menu-popover label:hover {
  color: var(--primary);
  background: var(--surface-hover);
}

.utility-menu-popover span {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.utility-menu-popover strong {
  color: var(--text);
  font-size: 12px;
}

.utility-menu-popover small {
  color: var(--text-faint);
  font-size: 10px;
}

.utility-menu-popover input {
  position: absolute;
  inset: 0;
  cursor: pointer;
  opacity: 0;
}

@media (max-width: 1279px) {
  .topbar {
    grid-template-columns: minmax(200px, 0.7fr) minmax(240px, 1fr) minmax(300px, 0.8fr);
    padding: 0 13px;
  }

  .contract-badge,
  .header-progress-issues,
  .header-progress-clear,
  .utility-menu summary span {
    display: none;
  }

  .utility-menu summary {
    width: 36px;
    padding: 0;
  }

  .utility-menu summary svg:last-child {
    display: none;
  }
}
</style>
