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
    expect(segments.find((item) => item.entity)?.text).toBe("口腔溃疡");
  });

  it("highlights each entity name when entities share one evidence sentence", () => {
    const text = "典型特征为皮疹、肉芽肿性关\n节炎和葡萄膜炎三联征。";
    const evidence = "典型特征为皮疹、肉芽肿性关节炎和葡萄膜炎三联征";
    const entities = [
      entity("皮疹", evidence),
      entity("肉芽肿性关节炎", evidence),
      entity("葡萄膜炎", evidence),
    ];
    for (const item of entities) {
      item.evidence_span = {
        start: 0,
        end: text.length - 1,
        raw_text: text.slice(0, -1),
        normalized_text: evidence,
      };
    }

    const segments = buildHighlightSegments(text, entities);

    expect(
      segments.filter((item) => item.entity).map((item) => item.text),
    ).toEqual(["皮疹", "肉芽肿性关\n节炎", "葡萄膜炎"]);
  });

  it("uses evidence ranges to distinguish repeated entity names", () => {
    const text = "皮疹缓解后再次皮疹。";
    const first = entity("皮疹");
    first.entity_id = "E-first";
    first.evidence_span = { start: 0, end: 2, raw_text: "皮疹" };
    const second = entity("皮疹");
    second.entity_id = "E-second";
    second.evidence_span = { start: 7, end: 9, raw_text: "皮疹" };

    const segments = buildHighlightSegments(text, [first, second]);
    const highlighted = segments.filter((item) => item.entity);

    expect(highlighted.map((item) => item.text)).toEqual(["皮疹", "皮疹"]);
    expect(highlighted.map((item) => item.entity?.entity_id)).toEqual([
      "E-first",
      "E-second",
    ]);
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
