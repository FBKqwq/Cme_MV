// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ReviewNavigation from "./ReviewNavigation.vue";
import type { ChunkSummary, TaskInfo } from "../types";

const task = {
  document: {
    title: "多文档复验",
    schema_version: "3.6",
    total_chunks: 3,
    pdf_available: true,
  },
  documents: [
    { document_id: "DOC_A", title: "文档 A", chunk_count: 2, pdf_available: true },
    { document_id: "DOC_B", title: "文档 B", chunk_count: 1, pdf_available: true },
  ],
  progress: { approved: 1, total: 3, percent: 33, issues: 2, modified: 0 },
  input_hash: "hash",
  version: 0,
} satisfies TaskInfo;

const chunks: ChunkSummary[] = [
  {
    chunk_id: "A_01",
    index: 1,
    section_title: "文档 A 第一节",
    page_start: 1,
    text_preview: "",
    entity_count: 2,
    relation_count: 1,
    issue_count: 0,
    status: "approved",
    approved: true,
    has_changes: false,
    _source_title: "文档 A",
    _doc_id: "DOC_A",
  },
  {
    chunk_id: "A_02",
    index: 2,
    section_title: "文档 A 第二节",
    page_start: 2,
    text_preview: "",
    entity_count: 1,
    relation_count: 0,
    issue_count: 2,
    status: "pending",
    approved: false,
    has_changes: false,
    _source_title: "文档 A",
    _doc_id: "DOC_A",
  },
  {
    chunk_id: "B_01",
    index: 3,
    section_title: "文档 B 第一节",
    page_start: 1,
    text_preview: "",
    entity_count: 3,
    relation_count: 2,
    issue_count: 0,
    status: "pending",
    approved: false,
    has_changes: false,
    _source_title: "文档 B",
    _doc_id: "DOC_B",
  },
];

function createWrapper(selectedPdf = "") {
  return mount(ReviewNavigation, {
    props: {
      task,
      chunks,
      filteredChunks: chunks,
      activeChunkId: "A_01",
      selectedPdf,
      searchQuery: "",
      pendingOnly: false,
      collapsed: false,
      statusLabel: (chunk: ChunkSummary) =>
        chunk.approved ? "已通过" : "待复验",
    },
  });
}

describe("ReviewNavigation", () => {
  it("renders PDF and Chunk as two linked lists", async () => {
    const wrapper = createWrapper();

    expect(wrapper.findAll(".document-row")).toHaveLength(2);
    expect(wrapper.text()).toContain("文档 A 第一节");
    expect(wrapper.text()).not.toContain("文档 B 第一节");

    await wrapper.findAll(".document-row")[1].trigger("click");
    expect(wrapper.emitted("update:selectedPdf")?.[0]).toEqual(["文档 B"]);

    await wrapper.setProps({ selectedPdf: "文档 B" });
    expect(wrapper.text()).toContain("文档 B 第一节");
    expect(wrapper.text()).not.toContain("文档 A 第一节");
  });

  it("emits the selected Chunk id", async () => {
    const wrapper = createWrapper("文档 A");

    await wrapper.findAll(".chunk-row")[1].trigger("click");

    expect(wrapper.emitted("selectChunk")?.[0]).toEqual(["A_02"]);
  });

  it("keeps search, filter and collapse actions in one compact toolbar", async () => {
    const wrapper = createWrapper("文档 A");
    const toolbar = wrapper.get(".chunk-tools");

    expect(toolbar.find(".search-field").exists()).toBe(true);
    expect(toolbar.find('[aria-label="仅看待复验"]').exists()).toBe(true);
    expect(toolbar.find('[aria-label="折叠 Chunk 导航"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain("文档与 Chunk");

    await toolbar.get('[aria-label="仅看待复验"]').trigger("click");
    expect(wrapper.emitted("update:pendingOnly")?.[0]).toEqual([true]);
  });
});
