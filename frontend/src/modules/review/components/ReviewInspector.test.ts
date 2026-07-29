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

const pending: EntityRecord = {
  entity_id: "ENTITY_PENDING",
  chunk_id: "CHUNK_01",
  name: "待处理实体",
  entity_type: "diseases",
  evidence_text: "待处理证据",
  status: "pending",
  _review: { ...review },
};

const accepted: EntityRecord = {
  ...pending,
  entity_id: "ENTITY_ACCEPTED",
  name: "已处理实体",
  status: "accepted",
};

const detail = {
  chunk: { chunk_id: "CHUNK_01", text: "测试证据" },
  entities: [pending, accepted],
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
  name: "",
  entity_type: "diseases",
  evidence_text: "",
  scope: "current",
};

function createWrapper(showAdd = false) {
  return mount(EntityReviewPanel, {
    props: {
      detail,
      pendingEntities: [pending],
      acceptedEntities: [accepted],
      selectedEntityId: "",
      editingId: "",
      showAdd,
      draft,
      entityTypeColors: { diseases: "#fee2e2" },
      entityTypeLabel: () => "疾病",
    },
  });
}

describe("EntityReviewPanel", () => {
  it("defaults to the pending queue and switches to accepted entities", async () => {
    const wrapper = createWrapper();

    expect(wrapper.text()).toContain("待处理实体");
    expect(wrapper.text()).not.toContain("已处理实体");

    await wrapper.get('[role="tab"][aria-selected="false"]').trigger("click");

    expect(wrapper.text()).toContain("已处理实体");
    expect(wrapper.text()).not.toContain("待处理实体");
  });

  it("renders exactly one create form", () => {
    const wrapper = createWrapper(true);

    expect(wrapper.findAll(".create-card")).toHaveLength(1);
    expect(wrapper.text()).toContain("新增实体");
  });
});
