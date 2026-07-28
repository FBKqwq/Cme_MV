import { describe, expect, it } from "vitest";
import { buildHighlightSegments } from "./highlight";
import type { EntityRecord } from "./types";

const entity = (name: string, evidence_text = name): EntityRecord => ({
  entity_id: `E-${name}`,
  chunk_id: "CH01",
  name,
  entity_type: "symptoms",
  evidence_text,
  _review: {
    operation: "source",
    deleted: false,
    added: false,
    modified: false,
  },
});

describe("buildHighlightSegments", () => {
  it("matches normalized Chinese punctuation and preserves source text", () => {
    const text = "主要表现为反复发作的口腔溃疡、生殖器溃疡。";
    const segments = buildHighlightSegments(text, [
      entity("口腔溃疡", "反复发作的口腔溃疡"),
    ]);
    expect(segments.map((item) => item.text).join("")).toBe(text);
    expect(segments.find((item) => item.entity)?.text).toBe("反复发作的口腔溃疡");
  });

  it("does not highlight deleted entities", () => {
    const deleted = entity("口腔溃疡");
    deleted._review.deleted = true;
    expect(buildHighlightSegments("口腔溃疡", [deleted])).toEqual([
      { text: "口腔溃疡" },
    ]);
  });
});
