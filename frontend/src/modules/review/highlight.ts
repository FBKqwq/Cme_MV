import type { EntityRecord } from "./types";

export interface HighlightSegment {
  text: string;
  entity?: EntityRecord;
}

interface NormalizedText {
  value: string;
  sourceIndexes: number[];
}

function normalizeWithMap(value: string): NormalizedText {
  let normalized = "";
  const sourceIndexes: number[] = [];
  for (let index = 0; index < value.length; index += 1) {
    const token = value[index].normalize("NFKC").toLowerCase();
    for (const char of token) {
      if (/[\s，。；、：！？,.!?;:（）()\[\]【】“”"'《》<>]/u.test(char)) {
        continue;
      }
      normalized += char;
      sourceIndexes.push(index);
    }
  }
  return { value: normalized, sourceIndexes };
}

function evidenceCandidates(entity: EntityRecord): string[] {
  const candidates: string[] = [];
  // evidence_span (singular) from entity_nodes.base.jsonl format - most precise
  if (entity.evidence_span?.normalized_text) {
    candidates.push(entity.evidence_span.normalized_text);
  }
  if (entity.evidence_span?.raw_text) {
    candidates.push(entity.evidence_span.raw_text);
  }
  // evidence_spans (array) from original format
  for (const span of entity.evidence_spans ?? []) {
    if (span.text) candidates.push(span.text);
  }
  if (entity.evidence_text) candidates.push(entity.evidence_text);
  if (entity.name) candidates.push(entity.name);
  return candidates.filter((v, i, a) => v.trim().length > 0 && a.indexOf(v) === i);
}

export function buildHighlightSegments(
  text: string,
  entities: EntityRecord[],
): HighlightSegment[] {
  const normalizedText = normalizeWithMap(text);
  const matches: Array<{ start: number; end: number; entity: EntityRecord }> = [];

  for (const entity of entities) {
    let best: { start: number; end: number } | undefined;
    for (const candidate of evidenceCandidates(entity)) {
      const normalizedCandidate = normalizeWithMap(candidate).value;
      if (!normalizedCandidate) continue;
      const found = normalizedText.value.indexOf(normalizedCandidate);
      if (found < 0) continue;
      const start = normalizedText.sourceIndexes[found];
      const end =
        normalizedText.sourceIndexes[found + normalizedCandidate.length - 1] + 1;
      best = { start, end };
      break;
    }
    if (best) matches.push({ ...best, entity });
  }

  const statePriority = (entity: EntityRecord) =>
    entity._review.deleted ? 0 : entity.status === "accepted" ? 2 : 1;
  matches.sort(
    (a, b) =>
      a.start - b.start ||
      statePriority(a.entity) - statePriority(b.entity) ||
      b.end - b.start - (a.end - a.start),
  );
  const accepted: typeof matches = [];
  let cursor = -1;
  for (const match of matches) {
    if (match.start < cursor) continue;
    accepted.push(match);
    cursor = match.end;
  }

  const segments: HighlightSegment[] = [];
  cursor = 0;
  for (const match of accepted) {
    if (match.start > cursor) segments.push({ text: text.slice(cursor, match.start) });
    segments.push({
      text: text.slice(match.start, match.end),
      entity: match.entity,
    });
    cursor = match.end;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor) });
  return segments;
}
