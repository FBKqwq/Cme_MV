<script setup lang="ts">
import { ExternalLink, X } from "lucide-vue-next";

defineProps<{
  open: boolean;
  url: string;
  page: number;
}>();

const emit = defineEmits<{
  close: [];
}>();
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
            <strong>PDF 第 {{ page }} 页</strong>
          </div>
          <div>
            <a
              class="icon-button subtle"
              :href="`${url}#page=${page}`"
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
              @click="emit('close')"
            >
              <X :size="18" />
            </button>
          </div>
        </header>
        <iframe
          :src="`${url}#page=${page}&view=FitH`"
          :title="`PDF 第 ${page} 页`"
        ></iframe>
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

.pdf-drawer header > div:last-child {
  display: flex;
  align-items: center;
  gap: 5px;
}

.pdf-drawer iframe {
  width: 100%;
  height: 100%;
  border: 0;
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
