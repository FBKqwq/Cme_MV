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

  it("keeps rejected entities available for red-border highlighting", () => {
    const deleted = entity("口腔溃疡");
    deleted._review.deleted = true;
    const segments = buildHighlightSegments("口腔溃疡", [deleted]);

    expect(segments[0].entity?._review.deleted).toBe(true);
  });

  it("prioritizes rejected entities when evidence spans overlap", () => {
    const accepted = entity("口腔溃疡");
    accepted.status = "accepted";
    const rejected = entity("口腔溃疡");
    rejected.entity_id = "E-rejected";
    rejected._review.deleted = true;

    const segments = buildHighlightSegments("口腔溃疡", [accepted, rejected]);

    expect(segments[0].entity?.entity_id).toBe("E-rejected");
  });
});
