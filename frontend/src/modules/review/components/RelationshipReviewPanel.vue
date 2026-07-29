<script setup lang="ts">
import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  FileText,
  GitBranch,
  PencilLine,
  Plus,
  Redo2,
  Trash2,
  Unlink2,
  X,
} from "lucide-vue-next";
import type {
  ChunkDetail,
  RelationDraft,
  RelationshipRecord,
} from "../types";

defineProps<{
  detail: ChunkDetail;
  relationships: RelationshipRecord[];
  selectedRelationId: string;
  editingId: string;
  showAdd: boolean;
  draft: RelationDraft;
  entityName: (entityId: string) => string;
  relationTypeLabel: (value: string) => string;
  relationChunkLabel: (relation: RelationshipRecord) => string;
}>();

const emit = defineEmits<{
  select: [relationId: string];
  edit: [relation: RelationshipRecord];
  cancelEdit: [];
  save: [relation: RelationshipRecord];
  approve: [relation: RelationshipRecord];
  remove: [relation: RelationshipRecord];
  restore: [relation: RelationshipRecord];
  create: [];
  cancelCreate: [];
  updateDraft: [patch: Partial<RelationDraft>];
}>();
</script>

<template>
  <div class="relationship-panel">
    <div class="relationship-summary">
      <span><GitBranch :size="14" />当前 Chunk 共 {{ relationships.length }} 条关系</span>
      <span v-if="relationships.some((item) => item.conflicts.length)" class="conflict-count">
        <AlertCircle :size="13" />
        {{ relationships.filter((item) => item.conflicts.length).length }} 条冲突
      </span>
    </div>

    <div class="review-list">
      <section v-if="showAdd" class="review-card create-card">
        <div class="card-title-row">
          <span class="type-icon new"><GitBranch :size="16" /></span>
          <div>
            <strong>新增关系</strong>
            <span>明确选择源实体、关系类型和目标实体</span>
          </div>
          <button
            class="icon-button subtle"
            type="button"
            aria-label="取消新增关系"
            @click="emit('cancelCreate')"
          >
            <X :size="17" />
          </button>
        </div>
        <div class="relation-editor">
          <label>
            <span>源实体</span>
            <span class="select-wrap">
              <select
                :value="draft.start_entity_id"
                @change="emit('updateDraft', { start_entity_id: ($event.target as HTMLSelectElement).value })"
              >
                <option v-for="option in detail.entity_options" :key="option.id" :value="option.id">
                  {{ option.name }}
                </option>
              </select>
              <ChevronDown :size="15" />
            </span>
          </label>
          <label>
            <span>关系类型</span>
            <span class="select-wrap">
              <select
                :value="draft.relation_type"
                @change="emit('updateDraft', { relation_type: ($event.target as HTMLSelectElement).value })"
              >
                <option v-for="type in detail.relation_types" :key="type.value" :value="type.value">
                  {{ type.label }}
                </option>
              </select>
              <ChevronDown :size="15" />
            </span>
          </label>
          <label>
            <span>目标实体</span>
            <span class="select-wrap">
              <select
                :value="draft.end_entity_id"
                @change="emit('updateDraft', { end_entity_id: ($event.target as HTMLSelectElement).value })"
              >
                <option v-for="option in detail.entity_options" :key="option.id" :value="option.id">
                  {{ option.name }}
                </option>
              </select>
              <ChevronDown :size="15" />
            </span>
          </label>
          <label>
            <span>证据原文</span>
            <textarea
              :value="draft.evidence_text"
              rows="3"
              @input="emit('updateDraft', { evidence_text: ($event.target as HTMLTextAreaElement).value })"
            ></textarea>
          </label>
        </div>
        <div class="edit-actions">
          <button class="button quiet compact" type="button" @click="emit('cancelCreate')">取消</button>
          <button class="button primary compact" type="button" @click="emit('create')">
            <Plus :size="15" />加入关系
          </button>
        </div>
      </section>

      <section
        v-for="relation in relationships"
        :key="relation.relation_id"
        class="review-card relation-card"
        :class="{
          selected: selectedRelationId === relation.relation_id,
          conflict: relation.conflicts.length,
          deleted: relation._review.deleted,
          changed: relation._review.modified || relation._review.added,
        }"
        :data-relation-card="relation.relation_id"
        @click="emit('select', relation.relation_id)"
      >
        <template v-if="editingId === relation.relation_id">
          <div class="card-title-row">
            <span class="type-icon edit"><Unlink2 :size="16" /></span>
            <div><strong>重绑关系</strong><span>端点修改会留下完整操作记录</span></div>
            <button
              class="icon-button subtle"
              type="button"
              aria-label="取消编辑关系"
              @click.stop="emit('cancelEdit')"
            >
              <X :size="17" />
            </button>
          </div>
          <div class="relation-editor" @click.stop>
            <label>
              <span>源实体</span>
              <span class="select-wrap">
                <select
                  :value="draft.start_entity_id"
                  @change="emit('updateDraft', { start_entity_id: ($event.target as HTMLSelectElement).value })"
                >
                  <option v-for="option in detail.entity_options" :key="option.id" :value="option.id">
                    {{ option.name }}
                  </option>
                </select>
                <ChevronDown :size="15" />
              </span>
            </label>
            <label>
              <span>关系类型</span>
              <span class="select-wrap">
                <select
                  :value="draft.relation_type"
                  @change="emit('updateDraft', { relation_type: ($event.target as HTMLSelectElement).value })"
                >
                  <option v-for="type in detail.relation_types" :key="type.value" :value="type.value">
                    {{ type.label }}
                  </option>
                </select>
                <ChevronDown :size="15" />
              </span>
            </label>
            <label>
              <span>目标实体</span>
              <span class="select-wrap">
                <select
                  :value="draft.end_entity_id"
                  @change="emit('updateDraft', { end_entity_id: ($event.target as HTMLSelectElement).value })"
                >
                  <option v-for="option in detail.entity_options" :key="option.id" :value="option.id">
                    {{ option.name }}
                  </option>
                </select>
                <ChevronDown :size="15" />
              </span>
            </label>
            <label>
              <span>证据原文</span>
              <textarea
                :value="draft.evidence_text"
                rows="3"
                @input="emit('updateDraft', { evidence_text: ($event.target as HTMLTextAreaElement).value })"
              ></textarea>
            </label>
          </div>
          <div class="edit-actions" @click.stop>
            <button class="button quiet compact" type="button" @click="emit('cancelEdit')">取消</button>
            <button class="button primary compact" type="button" @click="emit('save', relation)">
              <Check :size="15" />保存关系
            </button>
          </div>
        </template>

        <template v-else>
          <div v-if="relation.conflicts.length" class="conflict-banner">
            <AlertCircle :size="15" />
            <span>{{ relation.conflicts[0].message }}</span>
          </div>
          <div class="relation-flow">
            <div class="relation-node source">
              <span>源实体</span>
              <strong>{{ entityName(relation.start_entity_id) }}</strong>
            </div>
            <div class="relation-edge">
              <span>{{ relationTypeLabel(relation.relation_type) }}</span>
              <span class="edge-line"><i></i><ChevronRight :size="14" /></span>
            </div>
            <div class="relation-node target">
              <span>目标实体</span>
              <strong>{{ entityName(relation.end_entity_id) }}</strong>
            </div>
          </div>
          <div class="relation-meta">
            <span><FileText :size="13" />{{ relationChunkLabel(relation) }}</span>
            <span v-if="relation._review.added"><Plus :size="13" />医师新增</span>
            <span v-else-if="relation._review.modified"><PencilLine :size="13" />已修改</span>
            <span v-else><Clock3 :size="13" />待确认</span>
          </div>
          <blockquote v-if="relation.evidence_text" class="evidence-quote">
            {{ relation.evidence_text }}
          </blockquote>
          <div class="card-actions">
            <button
              v-if="relation._review.deleted"
              class="text-action restore"
              type="button"
              @click.stop="emit('restore', relation)"
            >
              <Redo2 :size="14" />恢复
            </button>
            <template v-else>
              <button class="text-action" type="button" @click.stop="emit('edit', relation)">
                <Unlink2 :size="14" />重绑 / 修改
              </button>
              <button
                class="text-action danger"
                type="button"
                @click.stop="emit('remove', relation)"
              >
                <Trash2 :size="14" />移除
              </button>
              <button
                v-if="!relation.conflicts.length"
                class="text-action accept"
                type="button"
                @click.stop="emit('approve', relation)"
              >
                <Check :size="14" />通过
              </button>
            </template>
          </div>
        </template>
      </section>

      <div v-if="!relationships.length && !showAdd" class="inspector-empty">
        <GitBranch :size="24" />
        <strong>当前 Chunk 没有关系</strong>
        <span>可以基于已经确认的实体建立一条新关系。</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.relationship-panel {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.relationship-summary {
  display: flex;
  min-height: 42px;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  color: var(--text-faint);
  border-bottom: 1px solid rgba(225, 231, 240, 0.72);
  background: #fbfcfe;
  font-size: 10px;
}

.relationship-summary span {
  display: flex;
  align-items: center;
  gap: 5px;
}

.relationship-summary .conflict-count {
  color: var(--amber);
}

.review-list {
  min-height: 0;
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 10px 11px 16px;
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

.review-card.selected {
  border-color: #aeb7ef;
  box-shadow: 0 0 0 2px rgba(89, 100, 223, 0.09);
}

.review-card.conflict {
  border-color: #e8c98f;
}

.review-card.deleted {
  opacity: 0.68;
}

.create-card,
.relation-card {
  padding: 13px;
}

.create-card {
  border-style: dashed;
  border-color: #cbd1f4;
  background: #fafaff;
}

.card-title-row,
.edit-actions,
.card-actions,
.relation-meta {
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
  color: var(--text-faint);
  font-size: 9px;
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

.relation-editor {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 9px;
}

.relation-editor label {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
  color: var(--text-faint);
  font-size: 9px;
  font-weight: 650;
}

.relation-editor label:last-child {
  grid-column: 1 / -1;
}

.relation-editor select,
.relation-editor textarea {
  width: 100%;
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 8px;
  outline: 0;
  background: #fff;
  font-size: 11px;
}

.relation-editor select {
  height: 34px;
  padding: 0 25px 0 9px;
  appearance: none;
}

.relation-editor textarea {
  padding: 8px 9px;
  resize: vertical;
}

.select-wrap {
  position: relative;
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

.conflict-banner {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: -13px -13px 12px;
  padding: 8px 10px;
  color: #9c661b;
  background: var(--amber-soft);
  font-size: 10px;
  line-height: 1.45;
}

.relation-flow {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 90px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
}

.relation-node {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
  padding: 9px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: #f8fafc;
}

.relation-node span,
.relation-edge > span:first-child {
  color: var(--text-faint);
  font-size: 8px;
}

.relation-node strong {
  overflow: hidden;
  color: #344057;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.relation-edge {
  display: flex;
  min-width: 0;
  align-items: center;
  flex-direction: column;
  gap: 4px;
  color: var(--primary);
  text-align: center;
}

.relation-edge > span:first-child {
  overflow: hidden;
  max-width: 90px;
  color: var(--primary);
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.edge-line {
  display: flex;
  width: 100%;
  align-items: center;
}

.edge-line i {
  height: 1px;
  flex: 1;
  background: #bfc6eb;
}

.relation-meta {
  gap: 10px;
  margin-top: 10px;
  color: var(--text-faint);
  font-size: 9px;
}

.relation-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.evidence-quote {
  margin: 10px 0 0;
  padding: 7px 9px;
  color: var(--text-soft);
  border-left: 2px solid #d9dfee;
  background: #f7f9fc;
  font-size: 10px;
  line-height: 1.55;
}

.card-actions {
  justify-content: flex-end;
  gap: 5px;
  margin: 11px -13px -13px;
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

.inspector-empty {
  display: flex;
  min-height: 280px;
  align-items: center;
  flex-direction: column;
  justify-content: center;
  gap: 7px;
  color: var(--text-faint);
  text-align: center;
}

.inspector-empty strong {
  color: var(--text-soft);
  font-size: 12px;
}

.inspector-empty span {
  font-size: 10px;
}
</style>
