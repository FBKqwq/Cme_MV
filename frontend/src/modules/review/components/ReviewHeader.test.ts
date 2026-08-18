// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ReviewHeader from "./ReviewHeader.vue";
import type { TaskInfo } from "../types";

const task = {
  document: {
    title: "多文档复验",
    schema_version: "3.6",
    total_chunks: 81,
    pdf_available: true,
  },
  documents: [],
  progress: {
    approved: 12,
    total: 81,
    percent: 15,
    issues: 24,
    modified: 3,
  },
  input_hash: "hash",
  version: 1,
} satisfies TaskInfo;

describe("ReviewHeader", () => {
  it("renders the review progress in the top bar", () => {
    const wrapper = mount(ReviewHeader, {
      props: {
        task,
        batches: [
          { id: "1", label: "第1批复验", status: "ready", error: "" },
          { id: "2", label: "第2批复验", status: "ready", error: "" },
        ],
        activeBatch: "1",
        batchSwitching: false,
        saveState: "idle",
        savingLabel: "修改自动保存",
        exportingPendingPdf: false,
      },
    });

    expect(wrapper.get(".header-progress").text()).toContain("12/81");
    expect(wrapper.get(".header-progress").text()).toContain("15%");
    expect(wrapper.get(".header-progress").text()).toContain("24 项需处理");
    expect(wrapper.get(".header-progress-value").attributes("style")).toContain(
      "width: 15%",
    );
    expect(wrapper.get(".topbar-actions").text()).toContain("导出未复验实体");
    expect(wrapper.get(".topbar-actions").text()).toContain("完成本篇复验");
  });

  it("emits the selected review batch", async () => {
    const wrapper = mount(ReviewHeader, {
      props: {
        task,
        batches: [
          { id: "1", label: "第1批复验", status: "ready", error: "" },
          { id: "2", label: "第2批复验", status: "ready", error: "" },
        ],
        activeBatch: "1",
        batchSwitching: false,
        saveState: "idle",
        savingLabel: "修改自动保存",
        exportingPendingPdf: false,
      },
    });

    await wrapper.get('[aria-label="切换复验批次"]').setValue("2");

    expect(wrapper.emitted("batch")).toEqual([["2"]]);
  });
});
