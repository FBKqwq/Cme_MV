<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { ChevronLeft, ChevronRight, RefreshCw, X } from "lucide-vue-next";
import type {
  PDFDocumentLoadingTask,
  PDFDocumentProxy,
  RenderTask,
} from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

const props = defineProps<{
  open: boolean;
  url: string;
  page: number;
}>();

const emit = defineEmits<{
  close: [];
}>();

const canvasRef = ref<HTMLCanvasElement>();
const stageRef = ref<HTMLElement>();
const currentPage = ref(1);
const totalPages = ref(0);
const loading = ref(false);
const errorMessage = ref("");

let loadingTask: PDFDocumentLoadingTask | undefined;
let pdfDocument: PDFDocumentProxy | undefined;
let renderTask: RenderTask | undefined;
let loadSequence = 0;
let pdfJsModule: typeof import("pdfjs-dist") | undefined;

const canGoPrevious = computed(() => currentPage.value > 1 && !loading.value);
const canGoNext = computed(
  () => currentPage.value < totalPages.value && !loading.value,
);

function clampPage(page: number) {
  return Math.min(Math.max(1, page), Math.max(1, totalPages.value));
}

async function getPdfJs() {
  const module = pdfJsModule ?? (await import("pdfjs-dist"));
  module.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;
  pdfJsModule = module;
  return module;
}

async function releaseDocument() {
  renderTask?.cancel();
  renderTask = undefined;

  const activeLoadingTask = loadingTask;
  loadingTask = undefined;
  if (activeLoadingTask) {
    await activeLoadingTask.destroy();
  }

  pdfDocument = undefined;
}

async function renderCurrentPage() {
  const document = pdfDocument;
  const canvas = canvasRef.value;
  const stage = stageRef.value;
  if (!document || !canvas || !stage) {
    return;
  }

  renderTask?.cancel();
  const page = await document.getPage(currentPage.value);
  const baseViewport = page.getViewport({ scale: 1 });
  const availableWidth = Math.max(280, stage.clientWidth - 32);
  const cssScale = Math.min(1.6, availableWidth / baseViewport.width);
  const outputScale = Math.min(window.devicePixelRatio || 1, 2);
  const viewport = page.getViewport({ scale: cssScale * outputScale });

  canvas.width = Math.floor(viewport.width);
  canvas.height = Math.floor(viewport.height);
  canvas.style.width = `${Math.floor(viewport.width / outputScale)}px`;
  canvas.style.height = `${Math.floor(viewport.height / outputScale)}px`;

  renderTask = page.render({ canvas, viewport });
  await renderTask.promise;
  renderTask = undefined;
}

async function loadPdf() {
  const sequence = ++loadSequence;
  await releaseDocument();
  totalPages.value = 0;
  errorMessage.value = "";

  if (!props.open || !props.url) {
    loading.value = false;
    return;
  }

  loading.value = true;
  currentPage.value = Math.max(1, props.page);

  try {
    await nextTick();
    const { getDocument } = await getPdfJs();
    const task = getDocument({ url: props.url });
    loadingTask = task;
    const document = await task.promise;

    if (sequence !== loadSequence || !props.open) {
      await task.destroy();
      return;
    }

    pdfDocument = document;
    totalPages.value = document.numPages;
    currentPage.value = clampPage(props.page);
    await nextTick();
    await renderCurrentPage();
  } catch (error) {
    if (sequence === loadSequence) {
      errorMessage.value =
        error instanceof Error ? error.message : "PDF 加载失败，请稍后重试";
    }
  } finally {
    if (sequence === loadSequence) {
      loading.value = false;
    }
  }
}

async function changePage(offset: number) {
  const nextPage = clampPage(currentPage.value + offset);
  if (nextPage === currentPage.value || loading.value) {
    return;
  }

  currentPage.value = nextPage;
  loading.value = true;
  errorMessage.value = "";
  try {
    await renderCurrentPage();
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "PDF 页面渲染失败";
  } finally {
    loading.value = false;
  }
}

watch(
  () => [props.open, props.url] as const,
  () => {
    void loadPdf();
  },
  { immediate: true },
);

watch(
  () => props.page,
  (page) => {
    if (!props.open || !pdfDocument) {
      return;
    }
    const nextPage = clampPage(page);
    if (nextPage !== currentPage.value) {
      currentPage.value = nextPage;
      void renderCurrentPage();
    }
  },
);

onBeforeUnmount(() => {
  loadSequence += 1;
  void releaseDocument();
});
</script>

<template>
  <Transition name="drawer">
    <div v-if="open" class="pdf-layer">
      <button
        class="drawer-backdrop"
        type="button"
        aria-label="关闭 PDF 预览"
        @click="emit('close')"
      ></button>
      <aside class="pdf-drawer" aria-label="PDF 原文预览">
        <header>
          <div>
            <span class="eyebrow">原始证据</span>
            <strong>PDF 第 {{ currentPage }} 页</strong>
          </div>
          <div class="drawer-actions">
            <button
              class="icon-button subtle"
              type="button"
              aria-label="重新加载 PDF"
              :disabled="loading"
              @click="loadPdf"
            >
              <RefreshCw :size="17" />
            </button>
            <button
              class="icon-button subtle"
              type="button"
              aria-label="关闭 PDF 预览"
              @click="emit('close')"
            >
              <X :size="18" />
            </button>
          </div>
        </header>

        <div class="pdf-toolbar" aria-label="PDF 翻页">
          <button
            class="icon-button subtle"
            type="button"
            aria-label="上一页"
            :disabled="!canGoPrevious"
            @click="changePage(-1)"
          >
            <ChevronLeft :size="18" />
          </button>
          <span>{{ currentPage }} / {{ totalPages || "—" }}</span>
          <button
            class="icon-button subtle"
            type="button"
            aria-label="下一页"
            :disabled="!canGoNext"
            @click="changePage(1)"
          >
            <ChevronRight :size="18" />
          </button>
        </div>

        <div ref="stageRef" class="pdf-stage">
          <div v-if="loading" class="pdf-state" role="status">
            <span class="loading-spinner"></span>
            正在加载 PDF…
          </div>
          <div v-else-if="errorMessage" class="pdf-state error-state" role="alert">
            <strong>PDF 暂时无法显示</strong>
            <span>{{ errorMessage }}</span>
            <button class="secondary-button" type="button" @click="loadPdf">
              重新加载
            </button>
          </div>
          <canvas
            ref="canvasRef"
            class="pdf-canvas"
            :class="{ hidden: loading || errorMessage }"
            :aria-label="`PDF 第 ${currentPage} 页内容`"
          ></canvas>
        </div>
      </aside>
    </div>
  </Transition>
</template>

<style scoped>
.pdf-layer {
  position: fixed;
  inset: 0;
  z-index: 80;
}

.drawer-backdrop {
  position: absolute;
  inset: 0;
  width: 100%;
  cursor: default;
  background: rgba(24, 32, 50, 0.28);
  backdrop-filter: blur(2px);
}

.pdf-drawer {
  position: absolute;
  top: 0;
  right: 0;
  display: flex;
  width: min(720px, 72vw);
  height: 100%;
  flex-direction: column;
  background: #fff;
  box-shadow: -18px 0 50px rgba(29, 40, 66, 0.2);
}

.pdf-drawer header {
  display: flex;
  min-height: 62px;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px 0 20px;
  border-bottom: 1px solid var(--border);
}

.pdf-drawer header > div:first-child {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.pdf-drawer header strong {
  color: var(--text);
  font-size: 13px;
}

.drawer-actions {
  display: flex;
  align-items: center;
  gap: 5px;
}

.pdf-toolbar {
  display: flex;
  min-height: 44px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-bottom: 1px solid var(--border);
  background: #f8faff;
}

.pdf-toolbar span {
  min-width: 66px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  text-align: center;
}

.icon-button:disabled {
  cursor: not-allowed;
  opacity: 0.38;
}

.pdf-stage {
  position: relative;
  flex: 1;
  overflow: auto;
  padding: 16px;
  background: #e9edf4;
  text-align: center;
}

.pdf-canvas {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 0 auto;
  background: #fff;
  box-shadow: 0 8px 24px rgba(35, 45, 66, 0.16);
}

.pdf-canvas.hidden {
  visibility: hidden;
}

.pdf-state {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--text-muted);
  font-size: 13px;
}

.loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid #cdd5e5;
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: pdf-spin 0.8s linear infinite;
}

.error-state {
  flex-direction: column;
  padding: 28px;
}

.error-state strong {
  color: var(--text);
  font-size: 15px;
}

.error-state span {
  max-width: 420px;
  line-height: 1.6;
}

@keyframes pdf-spin {
  to {
    transform: rotate(360deg);
  }
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity var(--ease);
}

.drawer-enter-active .pdf-drawer,
.drawer-leave-active .pdf-drawer {
  transition: transform var(--ease);
}

.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}

.drawer-enter-from .pdf-drawer,
.drawer-leave-to .pdf-drawer {
  transform: translateX(28px);
}
</style>
