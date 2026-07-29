// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReviewPdfDrawer from "./ReviewPdfDrawer.vue";

const pdfMocks = vi.hoisted(() => {
  const cancel = vi.fn();
  const render = vi.fn(() => ({
    promise: Promise.resolve(),
    cancel,
  }));
  const getPage = vi.fn(async () => ({
    getViewport: ({ scale }: { scale: number }) => ({
      width: 600 * scale,
      height: 800 * scale,
    }),
    render,
  }));
  const destroy = vi.fn(async () => undefined);
  const getDocument = vi.fn(() => ({
    promise: Promise.resolve({
      numPages: 3,
      getPage,
    }),
    destroy,
  }));

  return { cancel, destroy, getDocument, getPage, render };
});

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: {},
  getDocument: pdfMocks.getDocument,
}));

describe("ReviewPdfDrawer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the requested PDF page to canvas without an iframe", async () => {
    const wrapper = mount(ReviewPdfDrawer, {
      props: {
        open: true,
        url: "/api/review/pdf/DOC_A",
        page: 2,
      },
    });

    await flushPromises();

    expect(pdfMocks.getDocument).toHaveBeenCalledWith({
      url: "/api/review/pdf/DOC_A",
    });
    expect(pdfMocks.getPage).toHaveBeenCalledWith(2);
    expect(pdfMocks.render).toHaveBeenCalledOnce();
    expect(wrapper.find("iframe").exists()).toBe(false);
    expect(wrapper.get("canvas").attributes("aria-label")).toBe(
      "PDF 第 2 页内容",
    );
    expect(wrapper.get(".pdf-toolbar").text()).toContain("2 / 3");
  });

  it("changes pages inside the drawer", async () => {
    const wrapper = mount(ReviewPdfDrawer, {
      props: {
        open: true,
        url: "/api/review/pdf/DOC_A",
        page: 1,
      },
    });

    await flushPromises();
    await wrapper.get('button[aria-label="下一页"]').trigger("click");
    await flushPromises();

    expect(pdfMocks.getPage).toHaveBeenLastCalledWith(2);
    expect(wrapper.get(".pdf-toolbar").text()).toContain("2 / 3");
  });
});
