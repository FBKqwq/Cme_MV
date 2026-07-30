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
  entity_type: "",
  evidence_text: "待复验证据",
  status: "pending",
  _review: { ...review },
};

const rejected: EntityRecord = {
  ...accepted,
  entity_id: "ENTITY_REJECTED",
  name: "已拒绝实体",
  evidence_text: "已拒绝证据",
  status: "rejected",
  _review: { ...review },
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
  acceptedEntities?: EntityRecord[];
  pendingEntities?: EntityRecord[];
}) {
  return mount(EntityReviewPanel, {
    props: {
      detail,
      pendingEntities: options?.pendingEntities ?? [rejected, pending],
      acceptedEntities: options?.acceptedEntities ?? [accepted],
      selectedEntityId: "",
      editingId: options?.editingId ?? "",
      showAdd: options?.showAdd ?? false,
      draft,
      selectedEvidence: options?.selectedEvidence ?? "",
      entityTypeColors: { diseases: "#fee2e2" },
      entityTypeLabel: (value: string) => value ? "疾病" : "类型待定",
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
    expect(wrapper.get(".decision-lane").text()).toContain("类型待定");
  });

  it("orders rejected entities before review entities", () => {
    const cardElements = createWrapper().findAll(
      ".decision-lane .entity-card",
    );
    const cards = cardElements.map((card) => card.text());

    expect(cards[0]).toContain("已拒绝实体");
    expect(cards[1]).toContain("待复验实体");
    expect(cardElements[0].classes()).toContain("state-rejected");
  });

  it("keeps source accepted entities visible with reject as the only decision", async () => {
    const wrapper = createWrapper();
    const sourceCard = wrapper
      .findAll(".accepted-lane .entity-card")
      .find((card) => card.text().includes("已接受实体"));

    expect(sourceCard).toBeDefined();
    expect(sourceCard?.classes()).toContain("state-accepted");
    expect(sourceCard?.get(".machine-status").text()).toContain("机器判定");
    expect(sourceCard?.get(".machine-status").text()).toContain("接受");
    expect(sourceCard?.get(".review-action").text()).toBe("人工拒绝");
    expect(sourceCard?.text()).not.toContain("确认接受");
    expect(sourceCard?.text()).not.toContain("转回复验");
    expect(sourceCard?.findAll(".review-action")).toHaveLength(1);

    await sourceCard!.get(".review-action").trigger("click");
    expect(wrapper.emitted("reject")?.[0]).toEqual([accepted]);
    expect(wrapper.emitted("approve")).toBeUndefined();
    expect(wrapper.emitted("unapprove")).toBeUndefined();
  });

  it("keeps machine status separate from a human rejection", async () => {
    const humanRejected = {
      ...accepted,
      _review: { ...review, deleted: true },
    };
    const wrapper = createWrapper({ acceptedEntities: [humanRejected] });

    expect(wrapper.get(".accepted-lane").text()).toContain("已接受实体");
    expect(wrapper.get(".decision-lane").text()).not.toContain("已接受实体");
    expect(wrapper.get(".accepted-lane .entity-card").classes()).toContain(
      "state-rejected",
    );
    const sourceCard = wrapper.get(".accepted-lane .entity-card");
    expect(sourceCard.get(".machine-status").text()).toContain("接受");
    expect(sourceCard.get(".review-action").text()).toBe("撤销人工拒绝");

    await sourceCard.get(".review-action").trigger("click");
    expect(wrapper.emitted("restore")?.[0]).toEqual([humanRejected]);
  });

  it("allows a review entity to be manually approved without changing machine state", async () => {
    const wrapper = createWrapper({ pendingEntities: [pending] });
    const reviewCard = wrapper.get(".decision-lane .entity-card");

    expect(reviewCard.get(".machine-status").text()).toContain("复验");
    expect(reviewCard.get(".review-action.approve").text()).toBe("人工通过");

    await reviewCard.get(".review-action.approve").trigger("click");

    expect(wrapper.emitted("approve")?.[0]).toEqual([pending]);
  });

  it("allows a manual approval to be undone", async () => {
    const manuallyApproved = {
      ...pending,
      _review: { ...review, approved: true },
    };
    const wrapper = createWrapper({ pendingEntities: [manuallyApproved] });
    const reviewCard = wrapper.get(".decision-lane .entity-card");

    expect(reviewCard.classes()).toContain("state-accepted");
    expect(reviewCard.get(".machine-status").text()).toContain("复验");
    expect(reviewCard.get(".review-action.restore").text()).toBe("撤销人工通过");

    await reviewCard.get(".review-action.restore").trigger("click");

    expect(wrapper.emitted("unapprove")?.[0]).toEqual([manuallyApproved]);
  });

  it("replaces manual rejection with manual acceptance for a machine-rejected entity", async () => {
    const wrapper = createWrapper({ pendingEntities: [rejected] });
    const rejectedCard = wrapper.get(".decision-lane .entity-card");

    expect(rejectedCard.get(".machine-status").text()).toContain("拒绝");
    expect(rejectedCard.get(".review-action.approve").text()).toBe("人工接收");
    expect(rejectedCard.find(".review-action.danger").exists()).toBe(false);

    await rejectedCard.get(".review-action.approve").trigger("click");

    expect(wrapper.emitted("approve")?.[0]).toEqual([rejected]);
  });

  it("allows manual acceptance of a machine rejection to be undone", async () => {
    const manuallyAccepted = {
      ...rejected,
      _review: { ...review, approved: true },
    };
    const wrapper = createWrapper({ pendingEntities: [manuallyAccepted] });
    const acceptedCard = wrapper.get(".decision-lane .entity-card");

    expect(acceptedCard.classes()).toContain("state-accepted");
    expect(acceptedCard.get(".machine-status").text()).toContain("拒绝");
    expect(acceptedCard.get(".review-action.restore").text()).toBe("撤销人工接收");

    await acceptedCard.get(".review-action.restore").trigger("click");

    expect(wrapper.emitted("unapprove")?.[0]).toEqual([manuallyAccepted]);
  });

  it("keeps entity edits scoped to the current Chunk", () => {
    const wrapper = createWrapper({ editingId: pending.entity_id });

    expect(wrapper.text()).toContain("仅修改当前 Chunk 中的这次提及");
    expect(wrapper.text()).not.toContain("全部同源提及");
  });

  it("shows the full colored entity type only once", () => {
    const sourceCard = createWrapper().get(".accepted-lane .entity-card");

    expect(sourceCard.find(".entity-type-badge").exists()).toBe(false);
    expect(sourceCard.findAll(".entity-type")).toHaveLength(1);
    expect(sourceCard.get(".entity-type").text()).toBe("疾病");
    expect(sourceCard.get(".entity-type").attributes("style")).toContain(
      "background: rgb(254, 226, 226)",
    );
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
