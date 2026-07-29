<script setup lang="ts">
import {
  Check,
  CheckCircle2,
  ChevronDown,
  Clock3,
  PencilLine,
  Plus,
  Redo2,
  Sparkles,
  X,
  XCircle,
} from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import type {
  ChunkDetail,
  EntityDraft,
  EntityListFilter,
  EntityRecord,
} from "../types";

const props = defineProps<{
  detail: ChunkDetail;
  pendingEntities: EntityRecord[];
  acceptedEntities: EntityRecord[];
  selectedEntityId: string;
  editingId: string;
  showAdd: boolean;
  draft: EntityDraft;
  entityTypeColors: Record<string, string>;
  entityTypeLabel: (value: string) => string;
}>();

const emit = defineEmits<{
  select: [entityId: string];
  edit: [entity: EntityRecord];
  cancelEdit: [];
  save: [entity: EntityRecord];
  approve: [entity: EntityRecord];
  unapprove: [entity: EntityRecord];
  reject: [entity: EntityRecord];
  restore: [entity: EntityRecord];
  create: [];
  cancelCreate: [];
  updateDraft: [patch: Partial<EntityDraft>];
}>();

const filter = ref<EntityListFilter>("pending");
const displayedEntities = computed(() =>
  filter.value === "pending" ? props.pendingEntities : props.acceptedEntities,
);

watch(
  () => props.showAdd,
  (visible) => {
    if (visible) filter.value = "pending";
  },
);

watch(
  () => props.selectedEntityId,
  (id) => {
    if (id && props.acceptedEntities.some((entity) => entity.entity_id === id)) {
      filter.value = "accepted";
    }
  },
);

function evidence(entity: EntityRecord): string {
  return (
    entity.evidence_span?.normalized_text ||
    entity.evidence_span?.raw_text ||
    entity.evidence_text ||
    ""
  );
}
</script>

<template>
  <div class="entity-panel">
    <div class="entity-filter" role="tablist" aria-label="实体处理状态">
      <button
        type="button"
        role="tab"
        :aria-selected="filter === 'pending'"
        :class="{ active: filter === 'pending' }"
        @click="filter = 'pending'"
      >
        <Clock3 :size="14" />
        待处理
        <span>{{ pendingEntities.length }}</span>
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="filter === 'accepted'"
        :class="{ active: filter === 'accepted' }"
        @click="filter = 'accepted'"
      >
        <CheckCircle2 :size="14" />
        已处理
        <span>{{ acceptedEntities.length }}</span>
      </button>
    </div>

    <div class="review-list">
      <section v-if="showAdd" class="review-card create-card">
        <div class="card-title-row">
          <span class="type-icon new"><Sparkles :size="16" /></span>
          <div>
            <strong>新增实体</strong>
            <span>确认名称、类型和证据后加入当前 Chunk</span>
          </div>
          <button
            class="icon-button subtle"
            type="button"
            aria-label="取消新增实体"
            @click="emit('cancelCreate')"
          >
            <X :size="17" />
          </button>
        </div>
        <div class="edit-grid">
          <label>
            <span>实体名称</span>
            <input
              :value="draft.name"
              type="text"
              placeholder="输入实体名称"
              @input="emit('updateDraft', { name: ($event.target as HTMLInputElement).value })"
            />
          </label>
          <label>
            <span>实体类型</span>
            <span class="select-wrap">
              <select
                :value="draft.entity_type"
                @change="emit('updateDraft', { entity_type: ($event.target as HTMLSelectElement).value })"
              >
                <option
                  v-for="type in detail.entity_types"
                  :key="type.value"
                  :value="type.value"
                >
                  {{ type.label }}
                </option>
              </select>
              <ChevronDown :size="15" />
            </span>
          </label>
          <label class="full">
            <span>证据原文</span>
            <textarea
              :value="draft.evidence_text"
              rows="3"
              placeholder="输入支持该实体的原文"
              @input="emit('updateDraft', { evidence_text: ($event.target as HTMLTextAreaElement).value })"
            ></textarea>
          </label>
        </div>
        <div class="edit-actions">
          <button class="button quiet compact" type="button" @click="emit('cancelCreate')">
            取消
          </button>
          <button class="button primary compact" type="button" @click="emit('create')">
            <Plus :size="15" />加入实体
          </button>
        </div>
      </section>

      <section
        v-for="entity in displayedEntities"
        :key="entity.entity_id"
        class="review-card entity-card"
        :class="{
          selected: selectedEntityId === entity.entity_id,
          deleted: entity._review.deleted,
          changed: entity._review.modified || entity._review.added,
        }"
        :style="{ '--entity-color': entityTypeColors[entity.entity_type] || '#7180db' }"
        :data-entity-card="entity.entity_id"
        @click="emit('select', entity.entity_id)"
      >
        <template v-if="editingId === entity.entity_id">
          <div class="card-title-row">
            <span class="type-icon edit"><PencilLine :size="16" /></span>
            <div><strong>修改实体</strong><span>{{ entity.entity_id }}</span></div>
            <button
              class="icon-button subtle"
              type="button"
              aria-label="取消编辑"
              @click.stop="emit('cancelEdit')"
            >
              <X :size="17" />
            </button>
          </div>
          <div class="edit-grid" @click.stop>
            <label>
              <span>实体名称</span>
              <input
                :value="draft.name"
                type="text"
                @input="emit('updateDraft', { name: ($event.target as HTMLInputElement).value })"
              />
            </label>
            <label>
              <span>实体类型</span>
              <span class="select-wrap">
                <select
                  :value="draft.entity_type"
                  @change="emit('updateDraft', { entity_type: ($event.target as HTMLSelectElement).value })"
                >
                  <option
                    v-for="type in detail.entity_types"
                    :key="type.value"
                    :value="type.value"
                  >
                    {{ type.label }}
                  </option>
                </select>
                <ChevronDown :size="15" />
              </span>
            </label>
            <label class="full">
              <span>证据原文</span>
              <textarea
                :value="draft.evidence_text"
                rows="3"
                @input="emit('updateDraft', { evidence_text: ($event.target as HTMLTextAreaElement).value })"
              ></textarea>
            </label>
          </div>
          <div class="edit-actions" @click.stop>
            <button class="button quiet compact" type="button" @click="emit('cancelEdit')">
              取消
            </button>
            <button class="button primary compact" type="button" @click="emit('save', entity)">
              <Check :size="15" />保存修改
            </button>
          </div>
        </template>

        <template v-else>
          <div class="entity-card-head">
            <span
              class="entity-type-badge"
              :style="{ background: entityTypeColors[entity.entity_type] || '#eef0ff' }"
            >
              {{ entityTypeLabel(entity.entity_type).slice(0, 2) }}
            </span>
            <div class="entity-primary">
              <div class="entity-name-row">
                <strong>{{ entity.name }}</strong>
                <span class="entity-type">{{ entityTypeLabel(entity.entity_type) }}</span>
              </div>
              <div class="record-status">
                <template v-if="entity._review.deleted">
                  <XCircle :size="13" />不通过
                </template>
                <template v-else-if="entity.status === 'accepted'">
                  <CheckCircle2 :size="13" />已处理
                </template>
                <template v-else>
                  <Clock3 :size="13" />需要复验
                </template>
                <span v-if="entity.confidence != null">
                  · 置信度{{ Math.round(entity.confidence * 100) }}%
                </span>
              </div>
            </div>
          </div>

          <blockquote v-if="evidence(entity)" class="evidence-quote">
            {{ evidence(entity) }}
            <span v-if="entity.evidence_span?.start != null" class="evidence-position">
              [{{ entity.evidence_span.start }}-{{ entity.evidence_span.end }}]
            </span>
          </blockquote>

          <div class="card-actions">
            <button
              v-if="entity._review.deleted"
              class="text-action restore"
              type="button"
              @click.stop="emit('restore', entity)"
            >
              <Redo2 :size="14" />恢复
            </button>
            <template v-else-if="entity.status === 'accepted'">
              <button class="text-action" type="button" @click.stop="emit('edit', entity)">
                <PencilLine :size="14" />修改
              </button>
              <button
                class="text-action accept"
                type="button"
                @click.stop="emit('unapprove', entity)"
              >
                <Redo2 :size="14" />取消通过
              </button>
            </template>
            <template v-else>
              <button
                class="text-action danger"
                type="button"
                @click.stop="emit('reject', entity)"
              >
                <XCircle :size="14" />不通过
              </button>
              <button class="text-action" type="button" @click.stop="emit('edit', entity)">
                <PencilLine :size="14" />修改
              </button>
              <button
                class="text-action accept"
                type="button"
                @click.stop="emit('approve', entity)"
              >
                <Check :size="14" />通过
              </button>
            </template>
          </div>
        </template>
      </section>

      <div v-if="!displayedEntities.length && !showAdd" class="inspector-empty">
        <Clock3 v-if="filter === 'pending'" :size="23" />
        <CheckCircle2 v-else :size="23" />
        <strong>{{ filter === "pending" ? "当前 Chunk 没有待处理实体" : "暂无已处理实体" }}</strong>
        <span>
          {{
            filter === "pending"
              ? "可以从原文选择证据，或使用顶部按钮手动新增。"
              : "通过后的实体会集中显示在这里。"
          }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.entity-panel {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.entity-filter {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  padding: 9px 11px 7px;
  border-bottom: 1px solid rgba(225, 231, 240, 0.72);
  background: #fbfcfe;
}

.entity-filter button {
  display: flex;
  min-height: 34px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  color: var(--text-faint);
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  font-size: 11px;
  font-weight: 650;
}

.entity-filter button span {
  min-width: 19px;
  padding: 2px 5px;
  border-radius: 99px;
  background: #edf1f6;
  font-size: 9px;
}

.entity-filter button.active {
  color: var(--primary);
  border-color: #dce0fb;
  background: var(--primary-soft);
}

.entity-filter button.active span {
  background: #fff;
}

.review-list {
  min-height: 0;
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 10px 11px 16px;
  scroll-behavior: smooth;
  scrollbar-color: #cdd5e2 transparent;
  scrollbar-width: thin;
}

.review-card {
  position: relative;
  margin-bottom: 9px;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #fff;
  box-shadow: var(--shadow-xs);
}

.review-card:hover {
  border-color: #d3dbea;
  box-shadow: 0 7px 22px rgba(37, 49, 81, 0.055);
}

.entity-card {
  border-left: 3px solid var(--entity-color);
}

.entity-card.selected {
  border-color: #aeb7ef;
  border-left-color: var(--entity-color);
  box-shadow: 0 0 0 2px rgba(89, 100, 223, 0.09);
}

.entity-card.deleted {
  border-left-color: var(--red);
  opacity: 0.72;
}

.create-card {
  padding: 13px;
  border-style: dashed;
  border-color: #cbd1f4;
  background: #fafaff;
}

.card-title-row,
.entity-card-head,
.entity-name-row,
.record-status,
.edit-actions,
.card-actions {
  display: flex;
  align-items: center;
}

.card-title-row {
  gap: 9px;
  margin-bottom: 12px;
}

.card-title-row > div {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

.card-title-row strong {
  font-size: 12px;
}

.card-title-row span {
  overflow: hidden;
  color: var(--text-faint);
  font-size: 9px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.type-icon {
  display: grid;
  width: 31px;
  height: 31px;
  flex: 0 0 auto;
  place-items: center;
  color: var(--primary);
  border-radius: 9px;
  background: var(--primary-soft);
}

.entity-card-head {
  gap: 10px;
  padding: 12px 12px 8px;
}

.entity-type-badge {
  display: flex;
  width: 29px;
  height: 29px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  color: rgba(25, 34, 52, 0.68);
  border: 1px solid rgba(40, 54, 82, 0.07);
  border-radius: 7px;
  font-size: 10px;
  font-weight: 760;
}

.entity-primary {
  min-width: 0;
  flex: 1;
}

.entity-name-row {
  gap: 7px;
}

.entity-name-row strong {
  overflow: hidden;
  color: #2d374d;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entity-type {
  flex: 0 0 auto;
  padding: 2px 6px;
  color: var(--primary);
  border-radius: 99px;
  background: var(--primary-soft);
  font-size: 9px;
  font-weight: 650;
}

.record-status {
  gap: 4px;
  margin-top: 4px;
  color: var(--text-faint);
  font-size: 9px;
}

.evidence-quote {
  display: flex;
  gap: 8px;
  margin: 0 10px 9px 49px;
  padding: 7px 9px;
  color: var(--text-soft);
  border-left: 2px solid #d9dfee;
  border-radius: 0 7px 7px 0;
  background: #f7f9fc;
  font-size: 10px;
  line-height: 1.55;
}

.evidence-position {
  flex: 0 0 auto;
  margin-left: auto;
  color: var(--text-faint);
  font-family: monospace;
  font-size: 8px;
}

.card-actions {
  justify-content: flex-end;
  gap: 5px;
  padding: 7px 9px;
  border-top: 1px solid rgba(225, 231, 240, 0.72);
  background: #fbfcfe;
}

.text-action {
  display: flex;
  min-height: 27px;
  align-items: center;
  gap: 4px;
  padding: 0 7px;
  cursor: pointer;
  color: var(--text-soft);
  border-radius: 7px;
  background: transparent;
  font-size: 10px;
  font-weight: 630;
}

.text-action:hover {
  background: var(--surface-hover);
}

.text-action.accept,
.text-action.restore {
  color: var(--teal);
}

.text-action.danger {
  color: var(--red);
}

.edit-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.85fr);
  gap: 9px;
}

.entity-card .edit-grid {
  padding: 0 12px;
}

.edit-grid label {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
  color: var(--text-faint);
  font-size: 9px;
  font-weight: 650;
}

.edit-grid label.full {
  grid-column: 1 / -1;
}

.edit-grid input,
.edit-grid textarea,
.edit-grid select {
  width: 100%;
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 8px;
  outline: 0;
  background: #fff;
  font-size: 11px;
}

.edit-grid input,
.edit-grid select {
  height: 34px;
  padding: 0 9px;
}

.edit-grid textarea {
  padding: 8px 9px;
  resize: vertical;
}

.select-wrap {
  position: relative;
}

.select-wrap select {
  appearance: none;
}

.select-wrap svg {
  position: absolute;
  top: 50%;
  right: 8px;
  pointer-events: none;
  transform: translateY(-50%);
}

.edit-actions {
  justify-content: flex-end;
  gap: 7px;
  margin-top: 11px;
}

.entity-card .edit-actions {
  padding: 0 12px 12px;
}

.inspector-empty {
  display: flex;
  min-height: 260px;
  align-items: center;
  flex-direction: column;
  justify-content: center;
  gap: 7px;
  padding: 30px;
  color: var(--text-faint);
  text-align: center;
}

.inspector-empty strong {
  color: var(--text-soft);
  font-size: 12px;
}

.inspector-empty span {
  max-width: 260px;
  font-size: 10px;
  line-height: 1.5;
}
</style>
