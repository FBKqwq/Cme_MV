// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EvidencePane from "./EvidencePane.vue";
import type {
  ChunkDetail,
  ChunkSummary,
  EntityRecord,
} from "../types";

const machineRejected: EntityRecord = {
  entity_id: "ENTITY_REJECTED",
  chunk_id: "CHUNK_01",
  name: "机器拒绝实体",
  entity_type: "diseases",
  evidence_text: "机器拒绝实体",
  status: "rejected",
  _review: {
    operation: "source",
    deleted: false,
    added: false,
    modified: false,
  },
};

const currentSummary: ChunkSummary = {
  chunk_id: "CHUNK_01",
  index: 1,
  section_title: "临床表现",
  page_start: 1,
  text_preview: "机器拒绝实体",
  entity_count: 1,
  relation_count: 0,
  issue_count: 0,
  status: "pending",
  approved: false,
  has_changes: false,
};

function createWrapper(entity: EntityRecord) {
  const evidenceText = entity.evidence_text || entity.name;
  const detail: ChunkDetail = {
    chunk: {
      chunk_id: "CHUNK_01",
      section_title: "临床表现",
      section_path: ["正文", "临床表现"],
      page_start: 1,
      text: evidenceText,
    },
    entities: [entity],
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

  return mount(EvidencePane, {
    props: {
      detail,
      detailLoading: false,
      currentSummary,
      highlightedSegments: [
        {
          text: evidenceText,
          entity,
        },
      ],
      selectedEntityId: "",
      selectedEvidence: "",
      selectedEvidencePosition: { x: 0, y: 0 },
      currentPdfAvailable: false,
      currentPage: 1,
      activeChunkIndex: 0,
      totalChunks: 1,
    },
  });
}

describe("EvidencePane rejection presentation", () => {
  it("does not keep the human-rejection strike-through after restore", () => {
    const restored = {
      ...machineRejected,
      _review: {
        ...machineRejected._review,
        deleted: false,
      },
    };
    const highlight = createWrapper(restored).get(".entity-highlight");

    expect(highlight.classes()).toContain("rejected");
    expect(highlight.classes()).not.toContain("human-rejected");
  });

  it("adds the strike-through marker only for a human rejection", () => {
    const humanRejected = {
      ...machineRejected,
      _review: {
        ...machineRejected._review,
        operation: "delete" as const,
        deleted: true,
      },
    };
    const highlight = createWrapper(humanRejected).get(".entity-highlight");

    expect(highlight.classes()).toContain("rejected");
    expect(highlight.classes()).toContain("human-rejected");
  });

  it("shows a manually approved review entity as accepted", () => {
    const manuallyApproved = {
      ...machineRejected,
      status: "review",
      _review: {
        ...machineRejected._review,
        approved: true,
      },
    };
    const highlight = createWrapper(manuallyApproved).get(".entity-highlight");

    expect(highlight.classes()).toContain("accepted");
    expect(highlight.classes()).not.toContain("review");
    expect(highlight.classes()).not.toContain("human-rejected");
  });

  it("lets manual acceptance override a machine-rejected highlight", () => {
    const manuallyAccepted = {
      ...machineRejected,
      _review: {
        ...machineRejected._review,
        approved: true,
      },
    };
    const highlight = createWrapper(manuallyAccepted).get(".entity-highlight");

    expect(highlight.classes()).toContain("accepted");
    expect(highlight.classes()).not.toContain("rejected");
    expect(highlight.classes()).not.toContain("human-rejected");
  });
});
