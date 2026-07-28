<script setup lang="ts">
import {
  AlertCircle,
  ArrowLeftToLine,
  ArrowRight,
  BookOpenText,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Circle,
  Clock3,
  Download,
  ExternalLink,
  FileCheck2,
  FileText,
  Filter,
  GitBranch,
  Highlighter,
  LoaderCircle,
  Menu,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  PencilLine,
  Plus,
  Redo2,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  Unlink2,
  Upload,
  X,
  XCircle,
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
import { buildHighlightSegments } from "../modules/review/highlight";
import type {
  ChunkDetail,
  ChunkSummary,
  EntityRecord,
  RelationshipRecord,
  ReviewTab,
  SaveState,
  TaskInfo,
} from "../modules/review/types";

const router = useRouter();

type EntityDraft = {
  name: string;
  entity_type: string;
  evidence_text: string;
  scope: "current" | "all";
};

type RelationDraft = {
  start_entity_id: string;
  relation_type: string;
  end_entity_id: string;
  evidence_text: string;
};

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
const pdfList = computed(() => {
  const titles = new Set<string>();
  for (const c of chunks.value) {
    if (c._source_title) titles.add(c._source_title);
  }
  return Array.from(titles).sort();
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
  selectedPdf.value = selectedPdf.value === sourceTitle ? "" : sourceTitle;
  const first = chunks.value.find((c) => c._source_title === selectedPdf.value);
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
    <header class="topbar">
      <div class="brand-block">
        <button
          class="icon-button subtle mobile-menu"
          type="button"
          aria-label="展开 Chunk 导航"
          @click="leftCollapsed = !leftCollapsed"
        >
          <Menu :size="19" />
        </button>
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
        <span class="document-title">{{ task.document.title }}</span>
        <span class="contract-badge">Graph Contract V{{ task.document.schema_version }}</span>
      </div>

      <div class="topbar-actions">
        <button class="button quiet desktop-action" type="button" @click="router.push('/')">
          <ArrowLeftToLine :size="16" />
          返回诊断系统
        </button>
        <div class="save-indicator" :class="saveState" role="status">
          <LoaderCircle v-if="saveState === 'saving'" :size="14" class="spin" />
          <CheckCircle2 v-else-if="saveState === 'saved'" :size="14" />
          <AlertCircle v-else-if="saveState === 'error'" :size="14" />
          <Circle v-else :size="10" />
          <span>{{ savingLabel }}</span>
        </div>
        <label class="button quiet desktop-action" type="button" style="position:relative;cursor:pointer">
          <Upload :size="16" />
          导入复验
          <input type="file" accept=".zip" style="position:absolute;inset:0;opacity:0;cursor:pointer" @change="importReview" />
        </label>
        <button class="button quiet desktop-action" type="button" @click="downloadDraft">
          <Download :size="16" />
          导出草稿
        </button>
        <button class="button primary" type="button" @click="finalizeReview">
          <FileCheck2 :size="16" />
          完成本篇复验
        </button>
      </div>
    </header>

    <main v-if="loading" class="workspace loading-layout" aria-busy="true">
      <aside class="skeleton-sidebar">
        <div class="skeleton line wide"></div>
        <div class="skeleton line"></div>
        <div v-for="item in 8" :key="item" class="skeleton chunk"></div>
      </aside>
      <section class="skeleton-reader">
        <div class="skeleton line half"></div>
        <div v-for="item in 12" :key="item" class="skeleton paragraph"></div>
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
      <aside class="chunk-sidebar" :class="{ collapsed: leftCollapsed }">
        <template v-if="!leftCollapsed">
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
                @click="leftCollapsed = true"
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

                    <div class="sidebar-section">
            <div class="sidebar-section-header">PDF 文件</div>
            <div class="chunk-list" aria-label="PDF 文件列表">
              <button
                v-for="pdf in pdfList"
                :key="pdf"
                class="chunk-row"
                :class="{ active: selectedPdf === pdf }"
                type="button"
                @click="selectPdf(pdf)"
              >
                <span class="chunk-index"><FileText :size="14" /></span>
                <span class="chunk-row-content">
                  <span class="chunk-row-title">{{ pdf.replace(/\u300a|\u300b/g, "") }}</span>
                  <span class="chunk-row-meta">
                    <span>{{ chunks.filter((c) => c._source_title === pdf).length }} 段</span>
                    <span>{{ chunks.filter((c) => c._source_title === pdf && c.approved).length }}/{{ chunks.filter((c) => c._source_title === pdf).length }} 通过</span>
                  </span>
                </span>
                <ChevronRight :size="15" class="chunk-arrow" />
              </button>
              <button
                v-if="!selectedPdf"
                class="chunk-row active"
                type="button"
                disabled
              >
                <span class="chunk-index"><FileText :size="14" /></span>
                <span class="chunk-row-content">
                  <span class="chunk-row-title">全部文档</span>
                  <span class="chunk-row-meta">
                    <span>{{ chunks.length }} 段</span>
                    <span>{{ chunks.filter((c) => c.approved).length }}/{{ chunks.length }} 通过</span>
                  </span>
                </span>
                <ChevronRight :size="15" class="chunk-arrow" />
              </button>
            </div>
          </div>

          <div class="chunk-tools">
            <label class="search-field">
              <Search :size="15" />
              <input v-model="searchQuery" type="search" placeholder="搜索章节或原文" />
            </label>
            <button
              class="filter-toggle"
              :class="{ active: pendingOnly }"
              type="button"
              :aria-pressed="pendingOnly"
              @click="pendingOnly = !pendingOnly"
            >
              <Filter :size="14" />
              仅看待复验
            </button>
          </div>

          <div v-if="selectedPdf" class="pdf-section-label">
            <span>{{ selectedPdf.replace(/\u300a|\u300b/g, "") }}</span>
            <span class="pdf-section-count">{{ filteredChunks.length }} 段</span>
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
              @click="selectChunk(chunk.chunk_id)"
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
              <span>没有符合条件的 Chunk</span>
              <button type="button" @click="pendingOnly = false; searchQuery = ''; selectedPdf = ''">
                清除筛选
              </button>
            </div>
          </div>
        </template>
        <button
          v-else
          class="collapsed-rail-button"
          type="button"
          aria-label="展开 Chunk 导航"
          @click="leftCollapsed = false"
        >
          <PanelLeftOpen :size="19" />
          <span>CHUNK</span>
        </button>
      </aside>

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
              <div class="breadcrumb" v-if="detail.chunk.section_path?.length">
                <template
                  v-for="(section, index) in detail.chunk.section_path"
                  :key="`${section}-${index}`"
                >
                  <span>{{ section }}</span>
                  <ChevronRight v-if="index < detail.chunk.section_path.length - 1" :size="12" />
                </template>
              </div>
            </div>
            <div class="reader-actions">
              <button
                class="page-link"
                type="button"
                :disabled="!currentPdfAvailable"
                @click="pdfOpen = true"
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
                @click="goRelative(-1)"
              >
                <ChevronLeft :size="18" />
              </button>
              <button
                class="icon-button subtle"
                type="button"
                :disabled="activeChunkIndex >= chunks.length - 1"
                aria-label="下一个 Chunk"
                @click="goRelative(1)"
              >
                <ChevronRight :size="18" />
              </button>
            </div>
          </div>

          <div class="evidence-context">
            <span><Highlighter :size="14" />点击高亮可定位抽取结果</span>
            <span>选中文字可快速新建实体</span>
          </div>

          <article class="evidence-reader" @mouseup="captureSelection">
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
                  @click.stop="selectHighlightedEntity(segment.entity)"
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
            @click="openCreateEntity()"
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
                <Clock3 v-else :size="15" />
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
                :disabled="activeChunkIndex >= chunks.length - 1"
                @click="goRelative(1)"
              >
                暂存并跳过
              </button>
              <button class="button approve" type="button" @click="approveAndNext">
                <CheckCircle2 :size="17" />
                通过并进入下一 Chunk
                <ArrowRight :size="16" />
              </button>
            </div>
          </footer>
        </template>
      </section>

      <div
        v-if="!rightCollapsed"
        class="resize-handle"
        role="separator"
        aria-label="调整证据与编辑器宽度"
        @pointerdown="beginResize"
      >
        <span></span>
      </div>

      <aside
        class="review-inspector"
        :class="{ collapsed: rightCollapsed }"
        :style="rightCollapsed ? undefined : { width: `${inspectorWidth}px` }"
      >
        <template v-if="!rightCollapsed && detail">
          <div class="inspector-head">
            <div class="tab-list" role="tablist" aria-label="复验结果类型">
              <button
                class="review-tab"
                :class="{ active: activeTab === 'entities' }"
                type="button"
                role="tab"
                :aria-selected="activeTab === 'entities'"
                @click="activeTab = 'entities'"
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
                @click="activeTab = 'relationships'"
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
              @click="rightCollapsed = true"
            >
              <PanelRightClose :size="18" />
            </button>
          </div>

          <div class="inspector-summary">
            <div>
              <span class="eyebrow">
                {{ activeTab === "entities" ? "提及级复验" : "关系级复验" }}
              </span>
              <p>
                {{
                  activeTab === "entities"
                    ? "修改默认只影响当前提及，不会静默覆盖同名实体。"
                    : "端点变更必须显式重绑，冲突关系会阻止通过。"
                }}
              </p>
            </div>
            <button
              class="button compact"
              type="button"
              @click="activeTab === 'entities' ? openCreateEntity('') : openCreateRelation()"
            >
              <Plus :size="15" />
              新增{{ activeTab === "entities" ? "实体" : "关系" }}
            </button>
          </div>

          <div v-if="activeTab === 'entities'" class="review-list">
            <section v-if="showAddEntity" class="review-card create-card">
              <div class="card-title-row">
                <span class="type-icon new"><Sparkles :size="16" /></span>
                <div>
                  <strong>新增实体</strong>
                  <span>证据已从原文选区带入</span>
                </div>
                <button
                  class="icon-button subtle"
                  type="button"
                  aria-label="取消新增实体"
                  @click="showAddEntity = false"
                >
                  <X :size="17" />
                </button>
              </div>
              <div class="edit-grid">
                <label>
                  <span>实体名称</span>
                  <input v-model="entityDraft.name" type="text" placeholder="输入实体名称" />
                </label>
                <label>
                  <span>实体类型</span>
                  <span class="select-wrap">
                    <select v-model="entityDraft.entity_type">
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
                    v-model="entityDraft.evidence_text"
                    rows="3"
                    placeholder="输入支持该实体的原文"
                  ></textarea>
                </label>
              </div>
              <div class="edit-actions">
                <button class="button quiet compact" type="button" @click="showAddEntity = false">
                  取消
                </button>
                <button class="button primary compact" type="button" @click="createEntity">
                  <Plus :size="15" />加入实体
                </button>
              </div>
            </section>

            <div class="entity-split-columns">
              <div class="entity-col pending-col">
                <div class="entity-col-header">
                  <Clock3 :size="14" />
                  <span>待处理</span>
                  <span class="col-count">{{ pendingEntities.length }}</span>
                </div>

                <section v-if="showAddEntity" class="review-card create-card">
                  <div class="card-title-row">
                    <span class="type-icon new"><Sparkles :size="16" /></span>
                    <div><strong>新增实体</strong><span>证据已从原文选区带入</span></div>
                    <button class="icon-button subtle" type="button" aria-label="取消新增实体" @click="showAddEntity = false"><X :size="17" /></button>
                  </div>
                  <div class="edit-grid">
                    <label><span>实体名称</span><input v-model="entityDraft.name" type="text" placeholder="输入实体名称" /></label>
                    <label>
                      <span>实体类型</span>
                      <span class="select-wrap">
                        <select v-model="entityDraft.entity_type">
                          <option v-for="type in detail.entity_types" :key="type.value" :value="type.value">{{ type.label }}</option>
                        </select>
                        <ChevronDown :size="15" />
                      </span>
                    </label>
                    <label class="full"><span>证据原文</span><textarea v-model="entityDraft.evidence_text" rows="3" placeholder="输入支持该实体的原文"></textarea></label>
                  </div>
                  <div class="edit-actions">
                    <button class="button quiet compact" type="button" @click="showAddEntity = false">取消</button>
                    <button class="button primary compact" type="button" @click="createEntity"><Plus :size="15" />加入实体</button>
                  </div>
                </section>

                <section
                  v-for="entity in pendingEntities"
                  :key="entity.entity_id"
                  class="review-card entity-card"
                  :class="{
                    selected: selectedEntityId === entity.entity_id,
                    deleted: entity._review.deleted,
                    changed: entity._review.modified || entity._review.added,
                  }"
                  :style="{ background: entityTypeColors[entity.entity_type] || 'rgba(255,255,255,0.9)' }"
                  :data-entity-card="entity.entity_id"
                  @click="selectedEntityId = entity.entity_id"
                >
                  <template v-if="entityEditingId === entity.entity_id">
                    <div class="card-title-row">
                      <span class="type-icon edit"><PencilLine :size="16" /></span>
                      <div><strong>修改实体</strong><span>{{ entity.entity_id }}</span></div>
                      <button class="icon-button subtle" type="button" aria-label="取消编辑" @click.stop="entityEditingId = ''"><X :size="17" /></button>
                    </div>
                    <div class="edit-grid" @click.stop>
                      <label><span>实体名称</span><input v-model="entityDraft.name" type="text" /></label>
                      <label>
                        <span>实体类型</span>
                        <span class="select-wrap">
                          <select v-model="entityDraft.entity_type">
                            <option v-for="type in detail.entity_types" :key="type.value" :value="type.value">{{ type.label }}</option>
                          </select>
                          <ChevronDown :size="15" />
                        </span>
                      </label>
                      <label class="full"><span>证据原文</span><textarea v-model="entityDraft.evidence_text" rows="3"></textarea></label>
                      <label class="scope-option full">
                        <input v-model="entityDraft.scope" type="checkbox" true-value="all" false-value="current" />
                        <span class="custom-check"><Check :size="12" /></span>
                        <span>应用到该规范中的全部提及<small>名称或类型变化后，相关关系仍需人工确认。</small></span>
                      </label>
                    </div>
                    <div class="edit-actions" @click.stop>
                      <button class="button quiet compact" type="button" @click="entityEditingId = ''">取消</button>
                      <button class="button primary compact" type="button" @click="saveEntity(entity)"><Check :size="15" />保存修改</button>
                    </div>
                  </template>
                  <template v-else>
                    <div class="entity-card-head">
                      <span class="entity-type-badge" :style="{ background: entityTypeColors[entity.entity_type] || '#7180db' }">
                        {{ entityTypeLabel(entity.entity_type).slice(0, 2) }}
                      </span>
                      <div class="entity-primary">
                        <div class="entity-name-row">
                          <strong>{{ entity.name }}</strong>
                          <span class="entity-type">{{ entityTypeLabel(entity.entity_type) }}</span>
                        </div>
                        <div class="record-status">
                          <template v-if="entity._review.deleted"><XCircle :size="13" />不通过</template>
                          <template v-else-if="entity._review.added"><Plus :size="13" />医师新增</template>
                          <template v-else-if="entity._review.modified"><PencilLine :size="13" />已修改</template>
                          <template v-else><Clock3 :size="13" />需要复验</template>
                          <span v-if="entity.confidence != null">· 置信度{{ Math.round(entity.confidence * 100) }}%</span>
                        </div>
                      </div>
                      <button class="icon-button subtle card-menu" type="button" aria-label="实体更多操作"><MoreHorizontal :size="17" /></button>
                    </div>
                    <blockquote v-if="entity.evidence_text || entity.evidence_span" class="evidence-quote">
                      {{ entity.evidence_span?.normalized_text || entity.evidence_span?.raw_text || entity.evidence_text }}
                      <span v-if="entity.evidence_span?.start != null" class="evidence-position">[{{ entity.evidence_span?.start }}-{{ entity.evidence_span?.end }}]</span>
                    </blockquote>
                    <div class="card-actions">
                      <button v-if="entity._review.deleted" class="text-action restore" type="button" @click.stop="restoreEntity(entity)"><Redo2 :size="14" />恢复</button>
                      <template v-else>
                        <button class="text-action" type="button" @click.stop="rejectEntity(entity)"><XCircle :size="14" />不通过</button>
                        <button class="text-action" type="button" @click.stop="editEntity(entity)"><PencilLine :size="14" />修改</button>
                        <button class="text-action accept" type="button" @click.stop="approveEntity(entity)"><Check :size="14" />通过</button>
                      </template>
                    </div>
                  </template>
                </section>

                <div v-if="!pendingEntities.length && !showAddEntity" class="inspector-empty entity-col-empty">
                  <Clock3 :size="20" />
                  <strong>当前 Chunk 没有待处理实体</strong>
                  <button class="button compact" type="button" @click="openCreateEntity('')"><Plus :size="15" />手动新增</button>
                </div>
              </div>

              <div class="entity-col accepted-col">
                <div class="entity-col-header">
                  <CheckCircle2 :size="14" />
                  <span>已处理</span>
                  <span class="col-count">{{ acceptedEntities.length }}</span>
                </div>

                <section
                  v-for="entity in acceptedEntities"
                  :key="entity.entity_id"
                  class="review-card entity-card"
                  :class="{
                    selected: selectedEntityId === entity.entity_id,
                    changed: entity._review.modified || entity._review.added,
                  }"
                  :style="{ background: entityTypeColors[entity.entity_type] || 'rgba(255,255,255,0.9)' }"
                  :data-entity-card="entity.entity_id"
                  @click="selectedEntityId = entity.entity_id"
                >
                  <template v-if="entityEditingId === entity.entity_id">
                    <div class="card-title-row">
                      <span class="type-icon edit"><PencilLine :size="16" /></span>
                      <div><strong>修改实体</strong><span>{{ entity.entity_id }}</span></div>
                      <button class="icon-button subtle" type="button" aria-label="取消编辑" @click.stop="entityEditingId = ''"><X :size="17" /></button>
                    </div>
                    <div class="edit-grid" @click.stop>
                      <label><span>实体名称</span><input v-model="entityDraft.name" type="text" /></label>
                      <label>
                        <span>实体类型</span>
                        <span class="select-wrap">
                          <select v-model="entityDraft.entity_type">
                            <option v-for="type in detail.entity_types" :key="type.value" :value="type.value">{{ type.label }}</option>
                          </select>
                          <ChevronDown :size="15" />
                        </span>
                      </label>
                      <label class="full"><span>证据原文</span><textarea v-model="entityDraft.evidence_text" rows="3"></textarea></label>
                    </div>
                    <div class="edit-actions" @click.stop>
                      <button class="button quiet compact" type="button" @click="entityEditingId = ''">取消</button>
                      <button class="button primary compact" type="button" @click="saveEntity(entity)"><Check :size="15" />保存修改</button>
                    </div>
                  </template>
                  <template v-else>
                    <div class="entity-card-head">
                      <span class="entity-type-badge" :style="{ background: entityTypeColors[entity.entity_type] || '#7180db' }">
                        {{ entityTypeLabel(entity.entity_type).slice(0, 2) }}
                      </span>
                      <div class="entity-primary">
                        <div class="entity-name-row">
                          <strong>{{ entity.name }}</strong>
                          <span class="entity-type">{{ entityTypeLabel(entity.entity_type) }}</span>
                        </div>
                        <div class="record-status">
                          <CheckCircle2 :size="13" />已处理
                          <span v-if="entity.confidence != null">· 置信度{{ Math.round(entity.confidence * 100) }}%</span>
                        </div>
                      </div>
                      <button class="icon-button subtle card-menu" type="button" aria-label="实体更多操作"><MoreHorizontal :size="17" /></button>
                    </div>
                    <blockquote v-if="entity.evidence_text || entity.evidence_span" class="evidence-quote">
                      {{ entity.evidence_span?.normalized_text || entity.evidence_span?.raw_text || entity.evidence_text }}
                      <span v-if="entity.evidence_span?.start != null" class="evidence-position">[{{ entity.evidence_span?.start }}-{{ entity.evidence_span?.end }}]</span>
                    </blockquote>
                    <div class="card-actions">
                      <button class="text-action" type="button" @click.stop="editEntity(entity)"><PencilLine :size="14" />修改</button>
                      <button class="text-action accept" type="button" @click.stop="unapproveEntity(entity)"><RotateCcw :size="14" />取消通过</button>
                    </div>
                  </template>
                </section>

                <div v-if="!acceptedEntities.length && !showAddEntity" class="inspector-empty entity-col-empty">
                  <CheckCircle2 :size="20" />
                  <strong>暂无已处理实体</strong>
                  <span>在待处理列中点击“通过”将实体移入此列</span>
                </div>
              </div>
            </div>
            </div>
<div v-else class="review-list relation-list">
            <section v-if="showAddRelation" class="review-card create-card">
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
                  @click="showAddRelation = false"
                >
                  <X :size="17" />
                </button>
              </div>
              <div class="relation-editor">
                <label>
                  <span>源实体</span>
                  <span class="select-wrap">
                    <select v-model="relationDraft.start_entity_id">
                      <option
                        v-for="option in detail.entity_options"
                        :key="option.id"
                        :value="option.id"
                      >
                        {{ option.name }}
                      </option>
                    </select>
                    <ChevronDown :size="15" />
                  </span>
                </label>
                <label>
                  <span>关系类型</span>
                  <span class="select-wrap">
                    <select v-model="relationDraft.relation_type">
                      <option
                        v-for="type in detail.relation_types"
                        :key="type.value"
                        :value="type.value"
                      >
                        {{ type.label }}
                      </option>
                    </select>
                    <ChevronDown :size="15" />
                  </span>
                </label>
                <label>
                  <span>目标实体</span>
                  <span class="select-wrap">
                    <select v-model="relationDraft.end_entity_id">
                      <option
                        v-for="option in detail.entity_options"
                        :key="option.id"
                        :value="option.id"
                      >
                        {{ option.name }}
                      </option>
                    </select>
                    <ChevronDown :size="15" />
                  </span>
                </label>
                <label>
                  <span>证据原文</span>
                  <textarea v-model="relationDraft.evidence_text" rows="3"></textarea>
                </label>
              </div>
              <div class="edit-actions">
                <button class="button quiet compact" type="button" @click="showAddRelation = false">
                  取消
                </button>
                <button class="button primary compact" type="button" @click="createRelation">
                  <Plus :size="15" />加入关系
                </button>
              </div>
            </section>

            <section
              v-for="relation in visibleRelationships"
              :key="relation.relation_id"
              class="review-card relation-card"
              :class="{
                selected: selectedRelationId === relation.relation_id,
                conflict: relation.conflicts.length,
                deleted: relation._review.deleted,
                changed: relation._review.modified || relation._review.added,
              }"
              :data-relation-card="relation.relation_id"
              @click="selectedRelationId = relation.relation_id"
            >
              <template v-if="relationEditingId === relation.relation_id">
                <div class="card-title-row">
                  <span class="type-icon edit"><Unlink2 :size="16" /></span>
                  <div>
                    <strong>重绑关系</strong>
                    <span>端点修改会留下完整操作记录</span>
                  </div>
                  <button
                    class="icon-button subtle"
                    type="button"
                    aria-label="取消编辑关系"
                    @click.stop="relationEditingId = ''"
                  >
                    <X :size="17" />
                  </button>
                </div>
                <div class="relation-editor" @click.stop>
                  <label>
                    <span>源实体</span>
                    <span class="select-wrap">
                      <select v-model="relationDraft.start_entity_id">
                        <option
                          v-for="option in detail.entity_options"
                          :key="option.id"
                          :value="option.id"
                        >
                          {{ option.name }}
                        </option>
                      </select>
                      <ChevronDown :size="15" />
                    </span>
                  </label>
                  <label>
                    <span>关系类型</span>
                    <span class="select-wrap">
                      <select v-model="relationDraft.relation_type">
                        <option
                          v-for="type in detail.relation_types"
                          :key="type.value"
                          :value="type.value"
                        >
                          {{ type.label }}
                        </option>
                      </select>
                      <ChevronDown :size="15" />
                    </span>
                  </label>
                  <label>
                    <span>目标实体</span>
                    <span class="select-wrap">
                      <select v-model="relationDraft.end_entity_id">
                        <option
                          v-for="option in detail.entity_options"
                          :key="option.id"
                          :value="option.id"
                        >
                          {{ option.name }}
                        </option>
                      </select>
                      <ChevronDown :size="15" />
                    </span>
                  </label>
                  <label>
                    <span>证据原文</span>
                    <textarea v-model="relationDraft.evidence_text" rows="3"></textarea>
                  </label>
                </div>
                <div class="edit-actions" @click.stop>
                  <button
                    class="button quiet compact"
                    type="button"
                    @click="relationEditingId = ''"
                  >
                    取消
                  </button>
                  <button
                    class="button primary compact"
                    type="button"
                    @click="saveRelation(relation)"
                  >
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
                  <span>
                    <FileText :size="13" />
                    {{ relationChunkLabel(relation) }}
                  </span>
                  <span v-if="relation._review.added"><Plus :size="13" />医师新增</span>
                  <span v-else-if="relation._review.modified"><PencilLine :size="13" />已修改</span>
                  <span v-else><Clock3 :size="13" />待确认</span>
                </div>
                <blockquote v-if="relation.evidence_text" class="evidence-quote relation-evidence">
                  {{ relation.evidence_text }}
                </blockquote>
                <div class="card-actions">
                  <button
                    v-if="relation._review.deleted"
                    class="text-action restore"
                    type="button"
                    @click.stop="restoreRelation(relation)"
                  >
                    <Redo2 :size="14" />恢复
                  </button>
                  <template v-else>
                    <button
                      class="text-action"
                      type="button"
                      @click.stop="editRelation(relation)"
                    >
                      <Unlink2 :size="14" />重绑 / 修改
                    </button>
                    <button
                      class="text-action danger"
                      type="button"
                      @click.stop="removeRelation(relation)"
                    >
                      <Trash2 :size="14" />移除
                    </button>
                    <button
                      v-if="!relation.conflicts.length"
                      class="text-action accept"
                      type="button"
                      @click.stop="approveRelation(relation)"
                    >
                      <Check :size="14" />通过
                    </button>
                  </template>
                </div>
              </template>
            </section>

            <div
              v-if="!visibleRelationships.length && !showAddRelation"
              class="inspector-empty"
            >
              <GitBranch :size="24" />
              <strong>当前 Chunk 没有关系</strong>
              <span>你可以基于已经确认的实体建立一条新关系。</span>
              <button class="button compact" type="button" @click="openCreateRelation">
                <Plus :size="15" />新增关系
              </button>
            </div>
          </div>

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
          @click="rightCollapsed = false"
        >
          <PanelRightOpen :size="19" />
          <span>复验</span>
        </button>
      </aside>
    </main>

    <Transition name="drawer">
      <div v-if="pdfOpen" class="pdf-layer">
        <button
          class="drawer-backdrop"
          type="button"
          aria-label="关闭 PDF 预览"
          @click="pdfOpen = false"
        ></button>
        <aside class="pdf-drawer" aria-label="PDF 原文预览">
          <header>
            <div>
              <span class="eyebrow">原始证据</span>
              <strong>PDF 第 {{ currentPage }} 页</strong>
            </div>
            <div>
              <a
                class="icon-button subtle"
                :href="`${reviewPdfUrl}#page=${currentPage}`"
                target="_blank"
                rel="noreferrer"
                aria-label="在新窗口打开 PDF"
              >
                <ExternalLink :size="17" />
              </a>
              <button
                class="icon-button subtle"
                type="button"
                aria-label="关闭 PDF 预览"
                @click="pdfOpen = false"
              >
                <X :size="18" />
              </button>
            </div>
          </header>
          <iframe
            :src="`${reviewPdfUrl}#page=${currentPage}&view=FitH`"
            :title="`PDF 第 ${currentPage} 页`"
          ></iframe>
        </aside>
      </div>
    </Transition>

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
        <button class="toast-close" type="button" aria-label="关闭提示" @click="toast.visible = false">
          <X :size="15" />
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped src="../styles/review.css"></style>
