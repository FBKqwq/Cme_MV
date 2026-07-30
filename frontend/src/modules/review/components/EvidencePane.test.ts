// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EvidencePane from "./EvidencePane.vue";
import type { ChunkDetail, ChunkSummary } from "../types";

const detail: ChunkDetail = {
  chunk: {
    chunk_id: "DOC_A_CH01",
    section_title: "临床表现",
    section_path: ["正文", "临床表现"],
    page_start: 1,
    text: "测试证据原文",
  },
  entities: [],
  relationships: [],
  entity_options: [],
  entity_types: [],
  relation_types: [],
  review: {
    status: "pending",
    has_changes: false,
    issue_count: 0,
  },
  version: 1,
};

const currentSummary: ChunkSummary = {
  chunk_id: "DOC_A_CH01",
  index: 1,
  section_title: "临床表现",
  page_start: 1,
  text_preview: "测试证据原文",
  entity_count: 0,
  relation_count: 0,
  issue_count: 0,
  status: "pending",
  approved: false,
  has_changes: false,
};

function createWrapper(activeChunkIndex = 0, totalChunks = 2) {
  return mount(EvidencePane, {
    props: {
      detail,
      detailLoading: false,
      currentSummary,
      highlightedSegments: [{ text: detail.chunk.text }],
      selectedEntityId: "",
      selectedEvidence: "",
      selectedEvidencePosition: { x: 0, y: 0 },
      currentPdfAvailable: false,
      currentPage: 1,
      activeChunkIndex,
      totalChunks,
    },
  });
}

describe("EvidencePane", () => {
  it("keeps the skip action in the Chunk toolbar and removes approve-next", async () => {
    const wrapper = createWrapper();
    const toolbar = wrapper.get(".reader-actions");
    const skipButton = toolbar
      .findAll("button")
      .find((button) => button.text().includes("暂存并跳过"));

    expect(skipButton).toBeDefined();
    expect(wrapper.text()).not.toContain("通过并进入下一 Chunk");

    await skipButton!.trigger("click");

    expect(wrapper.emitted("skip")).toHaveLength(1);
  });

  it("disables the skip action on the last Chunk", () => {
    const wrapper = createWrapper(1, 2);
    const skipButton = wrapper
      .get(".reader-actions")
      .findAll("button")
      .find((button) => button.text().includes("暂存并跳过"));

    expect(skipButton?.attributes("disabled")).toBeDefined();
  });
});
