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
import { computed, nextTick, ref, watch } from "vue";
import type { ChunkDetail, EntityDraft, EntityRecord } from "../types";

const props = defineProps<{
  detail: ChunkDetail;
  pendingEntities: EntityRecord[];
  acceptedEntities: EntityRecord[];
  selectedEntityId: string;
  editingId: string;
  showAdd: boolean;
  draft: EntityDraft;
  selectedEvidence: string;
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

const nameInput = ref<HTMLInputElement | null>(null);
const rejectedEntities = computed(() =>
  props.pendingEntities.filter((entity) => entity._review.deleted),
);
const reviewEntities = computed(() =>
  props.pendingEntities.filter((entity) => !entity._review.deleted),
);
const decisionEntities = computed(() => [
  ...rejectedEntities.value,
  ...reviewEntities.value,
]);
const editingEntity = computed(() =>
  props.detail.entities.find((entity) => entity.entity_id === props.editingId),
);
const canSubmit = computed(
  () => Boolean(props.draft.name.trim() && props.draft.evidence_text.trim()),
);
const lanes = computed(() => [
  {
    key: "accepted",
    title: "接受",
    description: "已确认可进入知识库",
    entities: props.acceptedEntities,
  },
  {
    key: "decision",
    title: "拒绝与复验",
    description: `${rejectedEntities.value.length} 拒绝 · ${reviewEntities.value.length} 复验`,
    entities: decisionEntities.value,
  },
]);

watch(
  () => props.editingId,
  async (id) => {
    if (!id) return;
    await nextTick();
    nameInput.value?.focus();
    nameInput.value?.select();
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

function reviewState(entity: EntityRecord): "accepted" | "rejected" | "review" {
  if (entity._review.deleted) return "rejected";
  return entity.status === "accepted" ? "accepted" : "review";
}

function stateLabel(entity: EntityRecord): string {
  const state = reviewState(entity);
  if (state === "rejected") return "拒绝";
  if (state === "accepted") return "接受";
  return "复验";
}

function submitEdit() {
  if (editingEntity.value && canSubmit.value) emit("save", editingEntity.value);
}

function handleEditorKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") {
    event.preventDefault();
    emit("cancelEdit");
  }
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    submitEdit();
  }
}
</script>

<template>
  <div class="entity-panel">
    <section
      v-if="editingEntity"
      class="entity-editor"
      @keydown="handleEditorKeydown"
    >
      <div class="editor-head">
        <span class="editor-icon"><PencilLine :size="15" /></span>
        <div>
          <strong>修改实体</strong>
          <span>Ctrl/⌘ + Enter 保存 · Esc 取消</span>
        </div>
        <button
          class="icon-button subtle"
          type="button"
          aria-label="取消编辑"
          @click="emit('cancelEdit')"
        >
          <X :size="16" />
        </button>
      </div>

      <div class="edit-grid">
        <label>
          <span>实体名称</span>
          <input
            ref="nameInput"
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
            <ChevronDown :size="14" />
          </span>
        </label>
        <label>
          <span>作用范围</span>
          <span class="select-wrap">
            <select
              :value="draft.scope"
              @change="emit('updateDraft', { scope: ($event.target as HTMLSelectElement).value as EntityDraft['scope'] })"
            >
              <option value="current">仅当前提及</option>
              <option value="all">全部同源提及</option>
            </select>
            <ChevronDown :size="14" />
          </span>
        </label>
        <label class="evidence-field">
          <span>
            证据原文
            <button
              v-if="selectedEvidence"
              type="button"
              @click="emit('updateDraft', { evidence_text: selectedEvidence })"
            >
              使用当前选区
            </button>
          </span>
          <textarea
            :value="draft.evidence_text"
            rows="2"
            @input="emit('updateDraft', { evidence_text: ($event.target as HTMLTextAreaElement).value })"
          ></textarea>
        </label>
      </div>

      <div class="editor-actions">
        <span v-if="!canSubmit">名称和证据不能为空</span>
        <button class="button quiet compact" type="button" @click="emit('cancelEdit')">
          取消
        </button>
        <button
          class="button primary compact"
          type="button"
          :disabled="!canSubmit"
          @click="submitEdit"
        >
          <Check :size="14" />保存修改
        </button>
      </div>
    </section>

    <section v-if="showAdd" class="entity-editor create-editor">
      <div class="editor-head">
        <span class="editor-icon"><Sparkles :size="15" /></span>
        <div><strong>新增实体</strong><span>加入当前 Chunk</span></div>
        <button
          class="icon-button subtle"
          type="button"
          aria-label="取消新增实体"
          @click="emit('cancelCreate')"
        >
          <X :size="16" />
        </button>
      </div>
      <div class="edit-grid create-grid">
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
            <ChevronDown :size="14" />
          </span>
        </label>
        <label class="evidence-field">
          <span>证据原文</span>
          <textarea
            :value="draft.evidence_text"
            rows="2"
            @input="emit('updateDraft', { evidence_text: ($event.target as HTMLTextAreaElement).value })"
          ></textarea>
        </label>
      </div>
      <div class="editor-actions">
        <button class="button quiet compact" type="button" @click="emit('cancelCreate')">
          取消
        </button>
        <button
          class="button primary compact"
          type="button"
          :disabled="!canSubmit"
          @click="emit('create')"
        >
          <Plus :size="14" />加入实体
        </button>
      </div>
    </section>

    <div class="review-columns">
      <section
        v-for="lane in lanes"
        :key="lane.key"
        class="review-lane"
        :class="`${lane.key}-lane`"
      >
        <header class="lane-head">
          <div>
            <CheckCircle2 v-if="lane.key === 'accepted'" :size="15" />
            <Clock3 v-else :size="15" />
            <strong>{{ lane.title }}</strong>
            <span>{{ lane.entities.length }}</span>
          </div>
          <small>{{ lane.description }}</small>
        </header>

        <div class="lane-list">
          <article
            v-for="entity in lane.entities"
            :key="entity.entity_id"
            class="entity-card"
            :class="[
              `state-${reviewState(entity)}`,
              { selected: selectedEntityId === entity.entity_id },
            ]"
            :data-entity-card="entity.entity_id"
            @click="emit('select', entity.entity_id)"
          >
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
                  <XCircle v-if="reviewState(entity) === 'rejected'" :size="12" />
                  <CheckCircle2 v-else-if="reviewState(entity) === 'accepted'" :size="12" />
                  <Clock3 v-else :size="12" />
                  {{ stateLabel(entity) }}
                  <span v-if="entity.confidence != null">
                    · {{ Math.round(entity.confidence * 100) }}%
                  </span>
                </div>
              </div>
              <button
                v-if="!entity._review.deleted"
                class="quick-edit"
                type="button"
                aria-label="修改实体"
                title="修改实体"
                @click.stop="emit('edit', entity)"
              >
                <PencilLine :size="14" />
              </button>
            </div>

            <blockquote v-if="evidence(entity)" class="evidence-quote">
              <span>{{ evidence(entity) }}</span>
              <small v-if="entity.evidence_span?.start != null">
                [{{ entity.evidence_span.start }}-{{ entity.evidence_span.end }}]
              </small>
            </blockquote>

            <footer class="card-actions">
              <button
                v-if="entity._review.deleted"
                class="text-action restore"
                type="button"
                @click.stop="emit('restore', entity)"
              >
                <Redo2 :size="13" />恢复
              </button>
              <template v-else-if="entity.status === 'accepted'">
                <button
                  class="text-action"
                  type="button"
                  @click.stop="emit('unapprove', entity)"
                >
                  <Redo2 :size="13" />转回复验
                </button>
              </template>
              <template v-else>
                <button
                  class="text-action danger"
                  type="button"
                  @click.stop="emit('reject', entity)"
                >
                  <XCircle :size="13" />拒绝
                </button>
                <button
                  class="text-action accept"
                  type="button"
                  @click.stop="emit('approve', entity)"
                >
                  <Check :size="13" />接受
                </button>
              </template>
            </footer>
          </article>

          <div v-if="!lane.entities.length" class="lane-empty">
            <CheckCircle2 v-if="lane.key === 'accepted'" :size="20" />
            <Clock3 v-else :size="20" />
            <span>{{ lane.key === "accepted" ? "暂无接受实体" : "暂无拒绝或复验实体" }}</span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.entity-panel {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  container-type: inline-size;
}

.entity-editor {
  flex: 0 0 auto;
  padding: 10px 12px;
  border-bottom: 1px solid #d9def1;
  background: #f8f9ff;
  box-shadow: 0 8px 22px rgba(40, 52, 84, 0.06);
}

.create-editor {
  background: #fbfcff;
}

.editor-head,
.editor-actions,
.entity-card-head,
.entity-name-row,
.record-status,
.card-actions,
.lane-head > div {
  display: flex;
  align-items: center;
}

.editor-head {
  gap: 8px;
  margin-bottom: 9px;
}

.editor-icon {
  display: grid;
  width: 29px;
  height: 29px;
  flex: 0 0 auto;
  place-items: center;
  color: var(--primary);
  border-radius: 8px;
  background: var(--primary-soft);
}

.editor-head > div {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 1px;
}

.editor-head strong {
  color: #303a50;
  font-size: 12px;
}

.editor-head span {
  color: var(--text-faint);
  font-size: 9px;
}

.edit-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(120px, 0.8fr) minmax(120px, 0.75fr);
  gap: 8px;
}

.create-grid {
  grid-template-columns: minmax(0, 1.2fr) minmax(130px, 0.8fr);
}

.edit-grid label {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
  color: var(--text-faint);
  font-size: 9px;
  font-weight: 650;
}

.edit-grid label > span:first-child {
  display: flex;
  min-height: 17px;
  align-items: center;
  justify-content: space-between;
}

.evidence-field {
  grid-column: 1 / -1;
}

.evidence-field > span button {
  cursor: pointer;
  color: var(--primary);
  background: transparent;
  font-size: 9px;
  font-weight: 650;
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
  height: 32px;
  padding: 0 8px;
}

.edit-grid textarea {
  padding: 7px 8px;
  resize: vertical;
}

.edit-grid input:focus,
.edit-grid textarea:focus,
.edit-grid select:focus {
  border-color: #b9c1f0;
  box-shadow: 0 0 0 3px rgba(89, 100, 223, 0.08);
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
  right: 7px;
  pointer-events: none;
  transform: translateY(-50%);
}

.editor-actions {
  justify-content: flex-end;
  gap: 7px;
  margin-top: 8px;
}

.editor-actions > span {
  margin-right: auto;
  color: var(--red);
  font-size: 9px;
}

.review-columns {
  display: grid;
  min-height: 0;
  flex: 1;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  background: #f4f6fa;
}

.review-lane {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
}

.review-lane + .review-lane {
  border-left: 1px solid var(--border);
}

.lane-head {
  display: flex;
  min-height: 48px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 10px;
  border-bottom: 1px solid var(--border);
  background: rgba(251, 252, 255, 0.96);
}

.lane-head > div {
  min-width: 0;
  gap: 5px;
}

.lane-head strong {
  color: #354057;
  font-size: 11px;
}

.lane-head span {
  min-width: 18px;
  padding: 2px 5px;
  border-radius: 99px;
  background: #edf1f6;
  font-size: 9px;
  text-align: center;
}

.lane-head small {
  overflow: hidden;
  color: var(--text-faint);
  font-size: 8px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.accepted-lane .lane-head svg {
  color: var(--teal);
}

.decision-lane .lane-head svg {
  color: var(--amber);
}

.lane-list {
  min-height: 0;
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 8px;
  scrollbar-color: #cdd5e2 transparent;
  scrollbar-width: thin;
}

.entity-card {
  --state-color: var(--amber);
  margin-bottom: 7px;
  overflow: hidden;
  cursor: pointer;
  border: 1px solid #dce2eb;
  border-left: 3px solid var(--state-color);
  border-radius: 10px;
  background: #fff;
  box-shadow: var(--shadow-xs);
}

.entity-card.state-accepted {
  --state-color: #242b38;
}

.entity-card.state-rejected {
  --state-color: var(--red);
}

.entity-card.selected {
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--state-color) 18%, transparent);
}

.entity-card-head {
  gap: 8px;
  padding: 9px 9px 6px;
}

.entity-type-badge {
  display: flex;
  width: 27px;
  height: 27px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  color: rgba(25, 34, 52, 0.68);
  border: 1px solid rgba(40, 54, 82, 0.07);
  border-radius: 7px;
  font-size: 9px;
  font-weight: 760;
}

.entity-primary {
  min-width: 0;
  flex: 1;
}

.entity-name-row {
  min-width: 0;
  gap: 5px;
}

.entity-name-row strong {
  overflow: hidden;
  color: #2d374d;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entity-type {
  flex: 0 0 auto;
  padding: 2px 5px;
  color: var(--primary);
  border-radius: 99px;
  background: var(--primary-soft);
  font-size: 8px;
  font-weight: 650;
}

.record-status {
  gap: 3px;
  margin-top: 3px;
  color: var(--state-color);
  font-size: 8px;
  font-weight: 650;
}

.quick-edit {
  display: grid;
  width: 26px;
  height: 26px;
  flex: 0 0 auto;
  cursor: pointer;
  place-items: center;
  color: var(--text-faint);
  border-radius: 7px;
  background: transparent;
}

.quick-edit:hover {
  color: var(--primary);
  background: var(--primary-soft);
}

.evidence-quote {
  display: flex;
  gap: 6px;
  margin: 0 8px 7px 44px;
  padding: 6px 7px;
  color: var(--text-soft);
  border-left: 2px solid #d9dfee;
  border-radius: 0 6px 6px 0;
  background: #f7f9fc;
  font-size: 9px;
  line-height: 1.5;
}

.evidence-quote span {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.evidence-quote small {
  flex: 0 0 auto;
  margin-left: auto;
  color: var(--text-faint);
  font-family: monospace;
  font-size: 7px;
}

.card-actions {
  min-height: 31px;
  justify-content: flex-end;
  gap: 4px;
  padding: 4px 7px;
  border-top: 1px solid rgba(225, 231, 240, 0.72);
  background: #fbfcfe;
}

.text-action {
  display: flex;
  min-height: 23px;
  align-items: center;
  gap: 3px;
  padding: 0 6px;
  cursor: pointer;
  color: var(--text-soft);
  border-radius: 6px;
  background: transparent;
  font-size: 9px;
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

.lane-empty {
  display: flex;
  min-height: 180px;
  align-items: center;
  flex-direction: column;
  justify-content: center;
  gap: 7px;
  color: var(--text-faint);
  font-size: 10px;
}

@container (max-width: 540px) {
  .review-columns {
    overflow-y: auto;
    grid-template-columns: 1fr;
  }

  .review-lane {
    min-height: 280px;
  }

  .review-lane + .review-lane {
    border-top: 1px solid var(--border);
    border-left: 0;
  }

  .lane-list {
    overflow: visible;
  }

  .edit-grid {
    grid-template-columns: 1fr 1fr;
  }

  .evidence-field {
    grid-column: 1 / -1;
  }
}
</style>
