// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  ChunkDetail,
  ChunkSummary,
  TaskInfo,
} from "../modules/review/types";

const { apiMock } = vi.hoisted(() => ({
  apiMock: vi.fn(),
}));

vi.mock("../modules/review/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../modules/review/api")>();
  return {
    ...actual,
    api: apiMock,
  };
});

import KnowledgeReviewView from "./KnowledgeReviewView.vue";

const task: TaskInfo = {
  document: {
    title: "实体复验测试",
    schema_version: "3.6",
    total_chunks: 2,
    pdf_available: false,
  },
  documents: [
    {
      document_id: "DOC_TEST",
      title: "测试文档",
      chunk_count: 2,
      pdf_available: false,
    },
  ],
  progress: {
    approved: 0,
    total: 2,
    percent: 0,
    issues: 0,
    modified: 0,
  },
  input_hash: "test-input-hash",
  version: 0,
};

const chunks: ChunkSummary[] = [
  {
    chunk_id: "CHUNK_01",
    index: 1,
    section_title: "第一节",
    text_preview: "待复验实体",
    entity_count: 1,
    relation_count: 0,
    issue_count: 0,
    status: "pending",
    approved: false,
    has_changes: false,
    _source_title: "测试文档",
    _doc_id: "DOC_TEST",
  },
  {
    chunk_id: "CHUNK_02",
    index: 2,
    section_title: "第二节",
    text_preview: "第二段原文",
    entity_count: 0,
    relation_count: 0,
    issue_count: 0,
    status: "pending",
    approved: false,
    has_changes: false,
    _source_title: "测试文档",
    _doc_id: "DOC_TEST",
  },
];

function chunkDetail(chunkId: string, version = 0): ChunkDetail {
  const first = chunkId === "CHUNK_01";
  return {
    chunk: {
      chunk_id: chunkId,
      section_title: first ? "第一节" : "第二节",
      section_path: ["正文", first ? "第一节" : "第二节"],
      text: first ? "待复验实体" : "第二段原文",
    },
    entities: first
      ? [
          {
            entity_id: "ENTITY_REVIEW",
            chunk_id: "CHUNK_01",
            name: "待复验实体",
            entity_type: "symptoms",
            evidence_text: "待复验实体",
            status: "review",
            _review: {
              operation: "source",
              deleted: false,
              added: false,
              modified: false,
              approved: false,
            },
          },
        ]
      : [],
    relationships: [],
    entity_options: [],
    entity_types: [
      {
        value: "symptoms",
        label: "症状与体征",
        contract_label: "Symptom",
      },
    ],
    relation_types: [],
    review: {
      status: "pending",
      has_changes: false,
      issue_count: 0,
    },
    version,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

async function mountReview() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: "/knowledge-review",
        component: KnowledgeReviewView,
      },
      {
        path: "/",
        component: { template: "<div>首页</div>" },
      },
    ],
  });
  await router.push("/knowledge-review");
  await router.isReady();
  const wrapper = mount(KnowledgeReviewView, {
    global: {
      plugins: [router],
    },
  });
  await flushPromises();
  return wrapper;
}

function chunkButton(wrapper: ReturnType<typeof mount>, title: string) {
  const button = wrapper
    .findAll(".chunk-row")
    .find((item) => item.text().includes(title));
  if (!button) throw new Error(`未找到 Chunk：${title}`);
  return button;
}

function withoutBatch(path: string) {
  return path.replace(/[?&]batch=[^&]+/, "");
}

describe("KnowledgeReviewView entity persistence", () => {
  beforeEach(() => {
    apiMock.mockReset();
    localStorage.clear();
  });

  it("saves a review entity as manually approved while preserving machine status", async () => {
    let savedBody:
      | {
          entities: Array<{ rejected: boolean; approved: boolean }>;
        }
      | undefined;

    apiMock.mockImplementation((path: string, options?: RequestInit) => {
      const endpoint = withoutBatch(path);
      if (endpoint === "/api/review/batches") {
        return Promise.resolve({
          items: [
            { id: "1", label: "第1批复验", status: "ready", error: "" },
          ],
          default_batch: "1",
        });
      }
      if (endpoint === "/api/review/task") return Promise.resolve(task);
      if (endpoint === "/api/review/chunks") {
        return Promise.resolve({ items: chunks });
      }
      if (endpoint === "/api/review/chunks/CHUNK_01" && !options?.method) {
        return Promise.resolve(chunkDetail("CHUNK_01"));
      }
      if (endpoint === "/api/review/chunks/CHUNK_02" && !options?.method) {
        return Promise.resolve(chunkDetail("CHUNK_02", 1));
      }
      if (
        endpoint === "/api/review/chunks/CHUNK_01/entities" &&
        options?.method === "PUT"
      ) {
        savedBody = JSON.parse(String(options.body));
        return Promise.resolve({ version: 1, changed: 1 });
      }
      throw new Error(`Unexpected API call: ${path}`);
    });

    const wrapper = await mountReview();
    const reviewCard = wrapper.get(".decision-lane .entity-card");

    expect(reviewCard.get(".machine-status").text()).toContain("复验");
    await reviewCard.get(".review-action.approve").trigger("click");
    await chunkButton(wrapper, "第二节").trigger("click");
    await flushPromises();

    expect(savedBody?.entities[0]).toMatchObject({
      rejected: false,
      approved: true,
    });
  });

  it("persists an undo made while the first Chunk save is still running", async () => {
    const firstSave = deferred<{ version: number; changed: number }>();
    const savedBodies: Array<{
      entities: Array<{ rejected: boolean; approved: boolean }>;
    }> = [];
    let saveCount = 0;

    apiMock.mockImplementation((path: string, options?: RequestInit) => {
      const endpoint = withoutBatch(path);
      if (endpoint === "/api/review/batches") {
        return Promise.resolve({
          items: [
            { id: "1", label: "第1批复验", status: "ready", error: "" },
          ],
          default_batch: "1",
        });
      }
      if (endpoint === "/api/review/task") return Promise.resolve(task);
      if (endpoint === "/api/review/chunks") {
        return Promise.resolve({ items: chunks });
      }
      if (endpoint === "/api/review/chunks/CHUNK_01" && !options?.method) {
        return Promise.resolve(chunkDetail("CHUNK_01"));
      }
      if (endpoint === "/api/review/chunks/CHUNK_02" && !options?.method) {
        return Promise.resolve(chunkDetail("CHUNK_02", 2));
      }
      if (
        endpoint === "/api/review/chunks/CHUNK_01/entities" &&
        options?.method === "PUT"
      ) {
        savedBodies.push(JSON.parse(String(options.body)));
        saveCount += 1;
        return saveCount === 1
          ? firstSave.promise
          : Promise.resolve({ version: 2, changed: 1 });
      }
      throw new Error(`Unexpected API call: ${path}`);
    });

    const wrapper = await mountReview();
    await wrapper.get(".review-action.danger").trigger("click");
    await chunkButton(wrapper, "第二节").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("正在保存当前 Chunk");
    await wrapper.get(".review-action.restore").trigger("click");
    firstSave.resolve({ version: 1, changed: 1 });
    await flushPromises();
    await flushPromises();

    expect(savedBodies).toHaveLength(2);
    expect(savedBodies[0].entities[0]).toMatchObject({
      rejected: true,
      approved: false,
    });
    expect(savedBodies[1].entities[0]).toMatchObject({
      rejected: false,
      approved: false,
    });
    expect(wrapper.text()).toContain("第二段原文");
  });

  it("restores the previous Chunk when the target Chunk fails to load", async () => {
    apiMock.mockImplementation((path: string, options?: RequestInit) => {
      const endpoint = withoutBatch(path);
      if (endpoint === "/api/review/batches") {
        return Promise.resolve({
          items: [
            { id: "1", label: "第1批复验", status: "ready", error: "" },
          ],
          default_batch: "1",
        });
      }
      if (endpoint === "/api/review/task") return Promise.resolve(task);
      if (endpoint === "/api/review/chunks") {
        return Promise.resolve({ items: chunks });
      }
      if (endpoint === "/api/review/chunks/CHUNK_01" && !options?.method) {
        return Promise.resolve(chunkDetail("CHUNK_01"));
      }
      if (endpoint === "/api/review/chunks/CHUNK_02" && !options?.method) {
        return Promise.reject(new Error("Chunk 加载失败"));
      }
      throw new Error(`Unexpected API call: ${path}`);
    });

    const wrapper = await mountReview();
    await chunkButton(wrapper, "第二节").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("切换失败：Chunk 加载失败");
    expect(wrapper.text()).toContain("待复验实体");
    expect(chunkButton(wrapper, "第一节").classes()).toContain("active");
  });

  it("reloads the workspace with the selected batch parameter", async () => {
    const requestedPaths: string[] = [];
    apiMock.mockImplementation((path: string) => {
      requestedPaths.push(path);
      const endpoint = withoutBatch(path);
      if (endpoint === "/api/review/batches") {
        return Promise.resolve({
          items: [
            { id: "1", label: "第1批复验", status: "ready", error: "" },
            { id: "2", label: "第2批复验", status: "ready", error: "" },
          ],
          default_batch: "1",
        });
      }
      if (endpoint === "/api/review/task") return Promise.resolve(task);
      if (endpoint === "/api/review/chunks") {
        return Promise.resolve({ items: chunks });
      }
      if (endpoint === "/api/review/chunks/CHUNK_01") {
        return Promise.resolve(chunkDetail("CHUNK_01"));
      }
      throw new Error(`Unexpected API call: ${path}`);
    });

    const wrapper = await mountReview();
    await wrapper.get('[aria-label="切换复验批次"]').setValue("2");
    await flushPromises();

    expect(requestedPaths).toContain("/api/review/task?batch=2");
    expect(requestedPaths).toContain("/api/review/chunks?batch=2");
    expect(requestedPaths).toContain("/api/review/chunks/CHUNK_01?batch=2");
    expect(localStorage.getItem("review-active-batch")).toBe("2");
  });
});
