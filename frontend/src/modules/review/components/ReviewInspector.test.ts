// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EntityReviewPanel from "./EntityReviewPanel.vue";
import type { ChunkDetail, EntityDraft, EntityRecord } from "../types";

const review = {
  operation: "source" as const,
  deleted: false,
  added: false,
  modified: false,
};

const accepted: EntityRecord = {
  entity_id: "ENTITY_ACCEPTED",
  chunk_id: "CHUNK_01",
  name: "已接受实体",
  entity_type: "diseases",
  evidence_text: "已接受证据",
  status: "accepted",
  _review: { ...review },
};

const pending: EntityRecord = {
  ...accepted,
  entity_id: "ENTITY_PENDING",
  name: "待复验实体",
  evidence_text: "待复验证据",
  status: "pending",
};

const rejected: EntityRecord = {
  ...accepted,
  entity_id: "ENTITY_REJECTED",
  name: "已拒绝实体",
  evidence_text: "已拒绝证据",
  status: "pending",
  _review: { ...review, deleted: true },
};

const detail = {
  chunk: { chunk_id: "CHUNK_01", text: "测试证据" },
  entities: [accepted, pending, rejected],
  relationships: [],
  entity_options: [],
  entity_types: [
    { value: "diseases", label: "疾病", contract_label: "疾病" },
  ],
  relation_types: [],
  review: { status: "pending", has_changes: false, issue_count: 0 },
  version: 1,
} satisfies ChunkDetail;

const draft: EntityDraft = {
  name: "待复验实体",
  entity_type: "diseases",
  evidence_text: "待复验证据",
  scope: "current",
};

function createWrapper(options?: {
  editingId?: string;
  showAdd?: boolean;
  selectedEvidence?: string;
}) {
  return mount(EntityReviewPanel, {
    props: {
      detail,
      pendingEntities: [rejected, pending],
      acceptedEntities: [accepted],
      selectedEntityId: "",
      editingId: options?.editingId ?? "",
      showAdd: options?.showAdd ?? false,
      draft,
      selectedEvidence: options?.selectedEvidence ?? "",
      entityTypeColors: { diseases: "#fee2e2" },
      entityTypeLabel: () => "疾病",
    },
  });
}

describe("EntityReviewPanel", () => {
  it("shows accepted and decision entities in two columns", () => {
    const wrapper = createWrapper();

    expect(wrapper.findAll(".review-lane")).toHaveLength(2);
    expect(wrapper.get(".accepted-lane").text()).toContain("已接受实体");
    expect(wrapper.get(".decision-lane").text()).toContain("已拒绝实体");
    expect(wrapper.get(".decision-lane").text()).toContain("待复验实体");
  });

  it("orders rejected entities before review entities", () => {
    const cards = createWrapper()
      .findAll(".decision-lane .entity-card")
      .map((card) => card.text());

    expect(cards[0]).toContain("已拒绝实体");
    expect(cards[1]).toContain("待复验实体");
  });

  it("supports selection evidence and keyboard save in the fixed editor", async () => {
    const wrapper = createWrapper({
      editingId: pending.entity_id,
      selectedEvidence: "原文新选区",
    });

    await wrapper.get(".evidence-field button").trigger("click");
    expect(wrapper.emitted("updateDraft")?.[0]).toEqual([
      { evidence_text: "原文新选区" },
    ]);

    await wrapper.get(".entity-editor").trigger("keydown", {
      key: "Enter",
      ctrlKey: true,
    });
    expect(wrapper.emitted("save")?.[0]).toEqual([pending]);
  });

  it("renders exactly one create editor", () => {
    const wrapper = createWrapper({ showAdd: true });

    expect(wrapper.findAll(".create-editor")).toHaveLength(1);
    expect(wrapper.text()).toContain("新增实体");
  });
});
