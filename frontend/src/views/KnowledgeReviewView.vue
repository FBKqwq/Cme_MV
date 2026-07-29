<script setup lang="ts">
import {
  AlertCircle,
  CheckCircle2,
  RotateCcw,
  X,
} from "lucide-vue-next";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from "vue";
import { useRouter } from "vue-router";
import { ApiError, api, mutation } from "../modules/review/api";
import EntityReviewPanel from "../modules/review/components/EntityReviewPanel.vue";
import EvidencePane from "../modules/review/components/EvidencePane.vue";
import RelationshipReviewPanel from "../modules/review/components/RelationshipReviewPanel.vue";
import ReviewHeader from "../modules/review/components/ReviewHeader.vue";
import ReviewInspector from "../modules/review/components/ReviewInspector.vue";
import ReviewNavigation from "../modules/review/components/ReviewNavigation.vue";
import ReviewPdfDrawer from "../modules/review/components/ReviewPdfDrawer.vue";
import { buildHighlightSegments } from "../modules/review/highlight";
import type {
  ChunkDetail,
  ChunkSummary,
  EntityDraft,
  EntityRecord,
  RelationDraft,
  RelationshipRecord,
  ReviewTab,
  SaveState,
  TaskInfo,
} from "../modules/review/types";

const router = useRouter();

const task = ref<TaskInfo | null>(null);
const chunks = ref<ChunkSummary[]>([]);
const detail = ref<ChunkDetail | null>(null);
const activeChunkId = ref("");
const activeTab = ref<ReviewTab>("entities");
const selectedEntityId = ref("");
const selectedRelationId = ref("");
const loading = ref(true);
const detailLoading = ref(false);
const errorMessage = ref("");
const pendingOnly = ref(false);
const searchQuery = ref("");
const leftCollapsed = ref(false);
const selectedPdf = ref("");
const rightCollapsed = ref(false);
const pdfOpen = ref(false);
const saveState = ref<SaveState>("idle");
const savingLabel = computed(() => {
  if (saveState.value === "saving") return "保存中";
  if (saveState.value === "saved") return "已保存";
  if (saveState.value === "error") return "保存失败";
  return "修改自动保存";
});
const inspectorWidth = ref(Number(localStorage.getItem("review-inspector-width")) || 430);
const entityEditingId = ref("");
const relationEditingId = ref("");
const showAddEntity = ref(false);
const showAddRelation = ref(false);
const selectedEvidence = ref("");
const selectedEvidencePosition = reactive({ x: 0, y: 0 });
const toast = reactive<{
  visible: boolean;
  message: string;
  actionLabel?: string;
  action?: () => Promise<void>;
}>({ visible: false, message: "" });
let toastTimer: number | undefined;

const entityDraft = reactive<EntityDraft>({
  name: "",
  entity_type: "",
  evidence_text: "",
  scope: "current",
});
const relationDraft = reactive<RelationDraft>({
  start_entity_id: "",
  relation_type: "",
  end_entity_id: "",
  evidence_text: "",
});

const activeChunkIndex = computed(() =>
  chunks.value.findIndex((item) => item.chunk_id === activeChunkId.value),
);
const currentSummary = computed(() => chunks.value[activeChunkIndex.value]);
const reviewPdfUrl = computed(() => {
  const documentId = currentSummary.value?._doc_id;
  if (!documentId) return "";
  return `/api/review/pdf/${encodeURIComponent(documentId)}`;
});
const currentPdfAvailable = computed(() => {
  const documentId = currentSummary.value?._doc_id;
  return Boolean(
    documentId
      && task.value?.documents.some(
        (document) =>
          document.document_id === documentId
          && document.pdf_available,
      ),
  );
});
const filteredChunks = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  return chunks.value.filter((chunk) => {
    if (pendingOnly.value && chunk.approved && chunk.issue_count === 0) return false;
    if (selectedPdf.value && chunk._source_title !== selectedPdf.value) return false;
    if (!query) return true;
    return (
      chunk.chunk_id.toLowerCase().includes(query) ||
      chunk.section_title.toLowerCase().includes(query) ||
      chunk.text_preview.toLowerCase().includes(query)
    );
  });
});
const highlightedSegments = computed(() =>
  detail.value
    ? buildHighlightSegments(detail.value.chunk.text, detail.value.entities)
    : [],
);
const visibleEntities = computed(() => detail.value?.entities ?? []);
const visibleRelationships = computed(() => detail.value?.relationships ?? []);

/** Entities that have been approved (status === "accepted" and not deleted) */
const acceptedEntities = computed(() =>
  visibleEntities.value.filter((e) =>
    !e._review?.deleted && e.status === "accepted"
  )
);

/** Entities that need review: "not passed" (deleted) sorted before "needs review" (pending) */
const pendingEntities = computed(() =>
  visibleEntities.value
    .filter((e) => e._review?.deleted || e.status !== "accepted")
    .sort((a, b) => {
      if (a._review?.deleted && !b._review?.deleted) return -1;
      if (!a._review?.deleted && b._review?.deleted) return 1;
      return 0;
    })
);

/** Background color for each entity type */
const entityTypeColors: Record<string, string> = {
  diseases: "#fee2e2",
  sub_diseases: "#ffedd5",
  symptoms: "#dbeafe",
  tests: "#fce7f3",
  etiologies: "#fef9c3",
  pathogeneses: "#f3e8ff",
  treatments: "#dcfce7",
  plans: "#cffafe",
};
const documentPercent = computed(() => task.value?.progress.percent ?? 0);
const currentPage = computed(() => detail.value?.chunk.page_start ?? 1);

function entityTypeLabel(value: string): string {
  return (
    detail.value?.entity_types.find((item) => item.value === value)?.label || value
  );
}

function relationTypeLabel(value: string): string {
  return (
    detail.value?.relation_types.find((item) => item.value === value)?.label ||
    value.replaceAll("_", " ")
  );
}

function entityName(entityId: string): string {
  return (
    detail.value?.entity_options.find((item) => item.id === entityId)?.name ||
    entityId.replace(/^CANONICAL_/, "")
  );
}

function relationChunkLabel(relation: RelationshipRecord): string {
  const chunks = new Set(
    [relation.source_chunk_id, relation.target_chunk_id].filter(Boolean),
  );
  if (!chunks.size || (chunks.size === 1 && chunks.has(activeChunkId.value))) {
    return "当前 Chunk";
  }
  return Array.from(chunks).join(" / ");
}

function statusLabel(chunk: ChunkSummary): string {
  if (chunk.issue_count) return `${chunk.issue_count} 个问题`;
  if (chunk.approved && chunk.has_changes) return "修改后通过";
  if (chunk.approved) return "已通过";
  if (chunk.has_changes) return "有修改";
  return "待复验";
}

function showToast(
  message: string,
  actionLabel?: string,
  action?: () => Promise<void>,
) {
  window.clearTimeout(toastTimer);
  toast.visible = true;
  toast.message = message;
  toast.actionLabel = actionLabel;
  toast.action = action;
  toastTimer = window.setTimeout(() => {
    toast.visible = false;
  }, action ? 7000 : 3200);
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "操作失败，请稍后重试";
}

async function loadTaskAndChunks(selectInitial = false) {
  const [taskResult, chunkResult] = await Promise.all([
    api<TaskInfo>("/api/review/task"),
    api<{ items: ChunkSummary[] }>("/api/review/chunks"),
  ]);
  task.value = taskResult;
  chunks.value = chunkResult.items;
  if (selectInitial && !activeChunkId.value) {
    const firstUseful =
      chunks.value.find((item) => item.entity_count || item.relation_count) ||
      chunks.value[0];
    if (firstUseful) activeChunkId.value = firstUseful.chunk_id;
  }
}

async function loadChunk(chunkId: string) {
  detailLoading.value = true;
  errorMessage.value = "";
  try {
    detail.value = await api<ChunkDetail>(
      `/api/review/chunks/${encodeURIComponent(chunkId)}`,
    );
    if (task.value) task.value.version = detail.value.version;
    selectedEntityId.value =
      detail.value.entities.find((item) => !item._review.deleted)?.entity_id || "";
    selectedRelationId.value =
      detail.value.relationships.find((item) => !item._review.deleted)
        ?.relation_id || "";
    entityEditingId.value = "";
    relationEditingId.value = "";
    showAddEntity.value = false;
    showAddRelation.value = false;
  } catch (error) {
    errorMessage.value = errorText(error);
  } finally {
    detailLoading.value = false;
  }
}

function selectChunk(chunkId: string) {
  const chunk = chunks.value.find((c) => c.chunk_id === chunkId);
  if (chunk && chunk._source_title) {
    selectedPdf.value = chunk._source_title;
  }
  activeChunkId.value = chunkId;
}

function selectPdf(sourceTitle: string) {
  selectedPdf.value = sourceTitle;
  const first = chunks.value.find((c) => c._source_title === sourceTitle);
  if (first) {
    activeChunkId.value = first.chunk_id;
  }
}

async function bootstrap() {
  loading.value = true;
  try {
    await loadTaskAndChunks(true);
    if (activeChunkId.value) await loadChunk(activeChunkId.value);
  } catch (error) {
    errorMessage.value = errorText(error);
  } finally {
    loading.value = false;
  }
}

async function refreshAfterMutation(preferredId?: string, kind?: ReviewTab) {
  await Promise.all([loadTaskAndChunks(), loadChunk(activeChunkId.value)]);
  if (preferredId && kind === "entities") selectedEntityId.value = preferredId;
  if (preferredId && kind === "relationships") selectedRelationId.value = preferredId;
}

function beginSaving() {
  saveState.value = "saving";
}

function finishSaving() {
  saveState.value = "saved";
  window.setTimeout(() => {
    if (saveState.value === "saved") saveState.value = "idle";
  }, 1800);
}

function failSaving(error: unknown) {
  saveState.value = "error";
  showToast(errorText(error));
}

async function performMutation(
  operation: () => Promise<{ version: number; [key: string]: unknown }>,
  preferredId?: string,
  kind?: ReviewTab,
) {
  beginSaving();
  try {
    await operation();
    await refreshAfterMutation(preferredId, kind);
    finishSaving();
  } catch (error) {
    failSaving(error);
    if (error instanceof ApiError && error.status === 409) {
      await refreshAfterMutation();
    }
    throw error;
  }
}

function editEntity(entity: EntityRecord) {
  selectedEntityId.value = entity.entity_id;
  entityEditingId.value = entity.entity_id;
  Object.assign(entityDraft, {
    name: entity.name,
    entity_type: entity.entity_type,
    evidence_text: entity.evidence_text || entity.name,
    scope: "current",
  });
  nextTick(() =>
    document
      .querySelector(`[data-entity-card="${entity.entity_id}"]`)
      ?.scrollIntoView({ behavior: "smooth", block: "nearest" }),
  );
}

function editRelation(relation: RelationshipRecord) {
  selectedRelationId.value = relation.relation_id;
  relationEditingId.value = relation.relation_id;
  Object.assign(relationDraft, {
    start_entity_id: relation.start_entity_id,
    relation_type: relation.relation_type,
    end_entity_id: relation.end_entity_id,
    evidence_text: relation.evidence_text || "",
  });
}

async function saveEntity(entity: EntityRecord) {
  try {
    await performMutation(
      () =>
        api(`/api/review/entities/${encodeURIComponent(entity.entity_id)}`, {
          ...mutation("PATCH", {
            base_version: detail.value!.version,
            chunk_id: activeChunkId.value,
            scope: entityDraft.scope,
            name: entityDraft.name,
            entity_type: entityDraft.entity_type,
            evidence_text: entityDraft.evidence_text,
          }),
        }),
      entity.entity_id,
      "entities",
    );
    entityEditingId.value = "";
  } catch {
    // feedback is handled centrally
  }
}

async function approveEntity(entity: EntityRecord) {
  try {
    await performMutation(
      () =>
        api(`/api/review/entities/${encodeURIComponent(entity.entity_id)}`, {
          ...mutation("PATCH", {
            base_version: detail.value!.version,
            chunk_id: activeChunkId.value,
            scope: "current",
            status: "accepted",
          }),
        }),
      entity.entity_id,
      "entities",
    );
    showToast("实体已通过");
  } catch {
    // feedback is handled centrally
  }
}

async function unapproveEntity(entity: EntityRecord) {
  try {
    await performMutation(
      () =>
        api(`/api/review/entities/${encodeURIComponent(entity.entity_id)}`, {
          ...mutation("PATCH", {
            base_version: detail.value!.version,
            chunk_id: activeChunkId.value,
            scope: "current",
            status: "pending",
          }),
        }),
      entity.entity_id,
      "entities",
    );
    showToast("已取消通过，放回待处理");
  } catch {
    // feedback is handled centrally
  }
}

async function rejectEntity(entity: EntityRecord) {
  try {
    await performMutation(
      () =>
        api(`/api/review/entities/${encodeURIComponent(entity.entity_id)}`, {
          ...mutation("DELETE", {
            base_version: detail.value!.version,
            chunk_id: activeChunkId.value,
          }),
        }),
      entity.entity_id,
      "entities",
    );
    showToast("实体已标记为不通过");
  } catch {
    // feedback is handled centrally
  }
}

async function restoreEntity(entity: EntityRecord) {
  try {
    await performMutation(
      () =>
        api(
          `/api/review/entities/${encodeURIComponent(entity.entity_id)}/restore`,
          {
            ...mutation("POST", {
              base_version: detail.value!.version,
              chunk_id: activeChunkId.value,
            }),
          },
        ),
      entity.entity_id,
      "entities",
    );
    showToast("实体已恢复");
  } catch {
    // feedback is handled centrally
  }
}

function openCreateEntity(evidence = selectedEvidence.value) {
  activeTab.value = "entities";
  rightCollapsed.value = false;
  showAddEntity.value = true;
  entityEditingId.value = "";
  Object.assign(entityDraft, {
    name: evidence.trim(),
    entity_type: detail.value?.entity_types[0]?.value || "diseases",
    evidence_text: evidence.trim(),
    scope: "current",
  });
}

async function createEntity() {
  if (!entityDraft.name.trim() || !entityDraft.evidence_text.trim()) {
    showToast("请补全实体名称和证据文本");
    return;
  }
  try {
    let createdId = "";
    beginSaving();
    const result = await api<{ entity_id: string; version: number }>(
      "/api/review/entities",
      {
        ...mutation("POST", {
          base_version: detail.value!.version,
          chunk_id: activeChunkId.value,
          name: entityDraft.name,
          entity_type: entityDraft.entity_type,
          evidence_text: entityDraft.evidence_text,
        }),
      },
    );
    createdId = result.entity_id;
    await refreshAfterMutation(createdId, "entities");
    finishSaving();
    showAddEntity.value = false;
    selectedEvidence.value = "";
    showToast("新实体已加入当前 Chunk");
  } catch (error) {
    failSaving(error);
  }
}

async function saveRelation(relation: RelationshipRecord) {
  try {
    await performMutation(
      () =>
        api(
          `/api/review/relationships/${encodeURIComponent(relation.relation_id)}`,
          {
            ...mutation("PATCH", {
              base_version: detail.value!.version,
              chunk_id: activeChunkId.value,
              ...relationDraft,
            }),
          },
        ),
      relation.relation_id,
      "relationships",
    );
    relationEditingId.value = "";
  } catch {
    // feedback is handled centrally
  }
}

async function approveRelation(relation: RelationshipRecord) {
  Object.assign(relationDraft, {
    start_entity_id: relation.start_entity_id,
    relation_type: relation.relation_type,
    end_entity_id: relation.end_entity_id,
    evidence_text: relation.evidence_text || "",
  });
  try {
    await performMutation(
      () =>
        api(
          `/api/review/relationships/${encodeURIComponent(relation.relation_id)}`,
          {
            ...mutation("PATCH", {
              base_version: detail.value!.version,
              chunk_id: activeChunkId.value,
              status: "accepted",
            }),
          },
        ),
      relation.relation_id,
      "relationships",
    );
    showToast("关系已通过");
  } catch {
    // feedback is handled centrally
  }
}

async function removeRelation(relation: RelationshipRecord) {
  try {
    await performMutation(
      () =>
        api(
          `/api/review/relationships/${encodeURIComponent(relation.relation_id)}`,
          {
            ...mutation("DELETE", {
              base_version: detail.value!.version,
              chunk_id: activeChunkId.value,
            }),
          },
        ),
      relation.relation_id,
      "relationships",
    );
    showToast("关系已移除", "撤销", async () => {
      await restoreRelation(relation);
    });
  } catch {
    // feedback is handled centrally
  }
}

async function restoreRelation(relation: RelationshipRecord) {
  try {
    await performMutation(
      () =>
        api(
          `/api/review/relationships/${encodeURIComponent(relation.relation_id)}/restore`,
          {
            ...mutation("POST", {
              base_version: detail.value!.version,
              chunk_id: activeChunkId.value,
            }),
          },
        ),
      relation.relation_id,
      "relationships",
    );
    showToast("关系已恢复");
  } catch {
    // feedback is handled centrally
  }
}

function openCreateRelation() {
  activeTab.value = "relationships";
  showAddRelation.value = true;
  relationEditingId.value = "";
  const relationType = detail.value?.relation_types[0]?.value || "";
  Object.assign(relationDraft, {
    start_entity_id: detail.value?.entity_options[0]?.id || "",
    relation_type: relationType,
    end_entity_id: detail.value?.entity_options[1]?.id || "",
    evidence_text: selectedEvidence.value || detail.value?.chunk.text.slice(0, 80) || "",
  });
}

async function createRelation() {
  if (
    !relationDraft.start_entity_id ||
    !relationDraft.end_entity_id ||
    !relationDraft.relation_type ||
    !relationDraft.evidence_text.trim()
  ) {
    showToast("请补全关系端点、类型和证据");
    return;
  }
  try {
    beginSaving();
    const result = await api<{ relation_id: string; version: number }>(
      "/api/review/relationships",
      {
        ...mutation("POST", {
          base_version: detail.value!.version,
          chunk_id: activeChunkId.value,
          ...relationDraft,
        }),
      },
    );
    await refreshAfterMutation(result.relation_id, "relationships");
    finishSaving();
    showAddRelation.value = false;
    showToast("新关系已加入当前 Chunk");
  } catch (error) {
    failSaving(error);
  }
}

async function approveAndNext() {
  if (!detail.value) return;
  beginSaving();
  try {
    await api(
      `/api/review/chunks/${encodeURIComponent(activeChunkId.value)}/approve`,
      mutation("POST", { base_version: detail.value.version }),
    );
    await loadTaskAndChunks();
    finishSaving();
    const current = activeChunkIndex.value;
    const next =
      chunks.value.slice(current + 1).find((item) => !item.approved) ||
      chunks.value[current + 1];
    if (next) {
      activeChunkId.value = next.chunk_id;
    } else {
      await loadChunk(activeChunkId.value);
      showToast("当前已是最后一个 Chunk");
    }
  } catch (error) {
    failSaving(error);
    if (error instanceof ApiError && error.status === 422) {
      activeTab.value = "relationships";
      rightCollapsed.value = false;
      const first = detail.value.relationships.find(
        (item) => item.conflicts.length > 0,
      );
      if (first) {
        selectedRelationId.value = first.relation_id;
        nextTick(() =>
          document
            .querySelector(`[data-relation-card="${first.relation_id}"]`)
            ?.scrollIntoView({ behavior: "smooth", block: "center" }),
        );
      }
    }
  }
}

function goRelative(direction: -1 | 1) {
  const next = chunks.value[activeChunkIndex.value + direction];
  if (next) activeChunkId.value = next.chunk_id;
}

async function finalizeReview() {
  if (!detail.value) return;
  beginSaving();
  try {
    await api("/api/review/finalize", {
      ...mutation("POST", {
        base_version: detail.value.version,
        chunk_id: activeChunkId.value,
      }),
    });
    finishSaving();
    window.location.assign("/api/review/export?final=true");
  } catch (error) {
    failSaving(error);
  }
}

async function importReview(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  if (!file.name.endsWith(".zip")) {
    showToast("请选择 ZIP 格式的复验导出包");
    return;
  }
  try {
    beginSaving();
    const arrayBuffer = await file.arrayBuffer();
    const result = await api<{ message: string; version: number; counts: Record<string, number> }>(
      "/api/review/import",
      {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: arrayBuffer,
      },
    );
    showToast(result.message || "复验状态已导入");
    await bootstrap();
    finishSaving();
  } catch (error) {
    failSaving(error);
  } finally {
    input.value = "";
  }
}

function downloadDraft() {
  window.location.assign("/api/review/export");
}

function selectHighlightedEntity(entity: EntityRecord) {
  activeTab.value = "entities";
  selectedEntityId.value = entity.entity_id;
  rightCollapsed.value = false;
  nextTick(() =>
    document
      .querySelector(`[data-entity-card="${entity.entity_id}"]`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" }),
  );
}

function captureSelection(event: MouseEvent) {
  const selection = window.getSelection();
  const value = selection?.toString().trim() || "";
  if (!value || value.length > 240) {
    selectedEvidence.value = "";
    return;
  }
  selectedEvidence.value = value;
  selectedEvidencePosition.x = Math.min(
    event.clientX,
    window.innerWidth - (rightCollapsed.value ? 180 : inspectorWidth.value + 180),
  );
  selectedEvidencePosition.y = Math.max(84, event.clientY - 44);
}

function beginResize(event: PointerEvent) {
  const startX = event.clientX;
  const startWidth = inspectorWidth.value;
  const move = (moveEvent: PointerEvent) => {
    inspectorWidth.value = Math.min(
      620,
      Math.max(360, startWidth + startX - moveEvent.clientX),
    );
  };
  const stop = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", stop);
    localStorage.setItem("review-inspector-width", String(inspectorWidth.value));
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", stop);
}

function handleKeyboard(event: KeyboardEvent) {
  if (event.key === "Escape") {
    pdfOpen.value = false;
    showAddEntity.value = false;
    showAddRelation.value = false;
    entityEditingId.value = "";
    relationEditingId.value = "";
    selectedEvidence.value = "";
  }
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    void approveAndNext();
  }
}

watch(activeChunkId, (chunkId) => {
  if (chunkId) void loadChunk(chunkId);
});

onMounted(() => {
  window.addEventListener("keydown", handleKeyboard);
  void bootstrap();
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeyboard);
  window.clearTimeout(toastTimer);
});
</script>

<template>
  <div class="review-shell">
    <ReviewHeader
      :task="task"
      :save-state="saveState"
      :saving-label="savingLabel"
      @back="router.push('/')"
      @import="importReview"
      @export="downloadDraft"
      @finalize="finalizeReview"
    />

    <main v-if="loading" class="workspace loading-layout" aria-busy="true">
      <aside class="skeleton-sidebar">
        <div class="skeleton line wide"></div>
        <div class="skeleton line"></div>
        <div v-for="item in 7" :key="item" class="skeleton chunk"></div>
      </aside>
      <section class="skeleton-reader">
        <div class="skeleton line half"></div>
        <div v-for="item in 10" :key="item" class="skeleton paragraph"></div>
      </section>
      <aside class="skeleton-inspector">
        <div class="skeleton line wide"></div>
        <div v-for="item in 4" :key="item" class="skeleton review"></div>
      </aside>
    </main>

    <main v-else-if="errorMessage && !detail" class="fatal-state">
      <div class="fatal-icon"><AlertCircle :size="25" /></div>
      <h1>复验任务暂时无法打开</h1>
      <p>{{ errorMessage }}</p>
      <button class="button primary" type="button" @click="bootstrap">
        <RotateCcw :size="16" />
        重新加载
      </button>
    </main>

    <main v-else class="workspace">
      <ReviewNavigation
        :task="task"
        :chunks="chunks"
        :filtered-chunks="filteredChunks"
        :active-chunk-id="activeChunkId"
        :selected-pdf="selectedPdf"
        :search-query="searchQuery"
        :pending-only="pendingOnly"
        :collapsed="leftCollapsed"
        :document-percent="documentPercent"
        :status-label="statusLabel"
        @update:selected-pdf="selectPdf"
        @update:search-query="searchQuery = $event"
        @update:pending-only="pendingOnly = $event"
        @update:collapsed="leftCollapsed = $event"
        @select-chunk="selectChunk"
        @clear-filters="pendingOnly = false; searchQuery = ''; selectedPdf = ''"
      />

      <EvidencePane
        :detail="detail"
        :detail-loading="detailLoading"
        :current-summary="currentSummary"
        :highlighted-segments="highlightedSegments"
        :selected-entity-id="selectedEntityId"
        :selected-evidence="selectedEvidence"
        :selected-evidence-position="selectedEvidencePosition"
        :current-pdf-available="currentPdfAvailable"
        :current-page="currentPage"
        :active-chunk-index="activeChunkIndex"
        :total-chunks="chunks.length"
        @open-pdf="pdfOpen = true"
        @relative="goRelative"
        @select-entity="selectHighlightedEntity"
        @capture-selection="captureSelection"
        @create-from-selection="openCreateEntity()"
        @approve-next="approveAndNext"
      />

      <div
        v-if="!rightCollapsed"
        class="resize-handle"
        role="separator"
        aria-label="调整证据与编辑器宽度"
        @pointerdown="beginResize"
      >
        <span></span>
      </div>

      <ReviewInspector
        :detail="detail"
        :task="task"
        :active-tab="activeTab"
        :collapsed="rightCollapsed"
        :width="inspectorWidth"
        @update:active-tab="activeTab = $event"
        @update:collapsed="rightCollapsed = $event"
        @add="activeTab === 'entities' ? openCreateEntity('') : openCreateRelation()"
      >
        <EntityReviewPanel
          v-if="detail && activeTab === 'entities'"
          :detail="detail"
          :pending-entities="pendingEntities"
          :accepted-entities="acceptedEntities"
          :selected-entity-id="selectedEntityId"
          :editing-id="entityEditingId"
          :show-add="showAddEntity"
          :draft="entityDraft"
          :entity-type-colors="entityTypeColors"
          :entity-type-label="entityTypeLabel"
          @select="selectedEntityId = $event"
          @edit="editEntity"
          @cancel-edit="entityEditingId = ''"
          @save="saveEntity"
          @approve="approveEntity"
          @unapprove="unapproveEntity"
          @reject="rejectEntity"
          @restore="restoreEntity"
          @create="createEntity"
          @cancel-create="showAddEntity = false"
          @update-draft="Object.assign(entityDraft, $event)"
        />

        <RelationshipReviewPanel
          v-else-if="detail"
          :detail="detail"
          :relationships="visibleRelationships"
          :selected-relation-id="selectedRelationId"
          :editing-id="relationEditingId"
          :show-add="showAddRelation"
          :draft="relationDraft"
          :entity-name="entityName"
          :relation-type-label="relationTypeLabel"
          :relation-chunk-label="relationChunkLabel"
          @select="selectedRelationId = $event"
          @edit="editRelation"
          @cancel-edit="relationEditingId = ''"
          @save="saveRelation"
          @approve="approveRelation"
          @remove="removeRelation"
          @restore="restoreRelation"
          @create="createRelation"
          @cancel-create="showAddRelation = false"
          @update-draft="Object.assign(relationDraft, $event)"
        />
      </ReviewInspector>
    </main>

    <ReviewPdfDrawer
      :open="pdfOpen"
      :url="reviewPdfUrl"
      :page="currentPage"
      @close="pdfOpen = false"
    />

    <Transition name="toast">
      <div v-if="toast.visible" class="toast" role="status">
        <CheckCircle2 :size="17" />
        <span>{{ toast.message }}</span>
        <button
          v-if="toast.action && toast.actionLabel"
          type="button"
          @click="toast.action(); toast.visible = false"
        >
          {{ toast.actionLabel }}
        </button>
        <button
          class="toast-close"
          type="button"
          aria-label="关闭提示"
          @click="toast.visible = false"
        >
          <X :size="15" />
        </button>
      </div>
    </Transition>
  </div>
</template>

<style src="../styles/review.css"></style>
