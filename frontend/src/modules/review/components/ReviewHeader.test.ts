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
        saveState: "idle",
        savingLabel: "修改自动保存",
      },
    });

    expect(wrapper.get(".header-progress").text()).toContain("12/81");
    expect(wrapper.get(".header-progress").text()).toContain("15%");
    expect(wrapper.get(".header-progress").text()).toContain("24 项需处理");
    expect(wrapper.get(".header-progress-value").attributes("style")).toContain(
      "width: 15%",
    );
  });
});
