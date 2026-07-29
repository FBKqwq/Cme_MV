import type { EntityRecord } from "./types";

export interface HighlightSegment {
  text: string;
  entity?: EntityRecord;
}

interface NormalizedText {
  value: string;
  sourceIndexes: number[];
}

interface TextRange {
  start: number;
  end: number;
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

function findNormalizedMatch(
  text: string,
  candidate: string,
  range: TextRange = { start: 0, end: text.length },
): TextRange | undefined {
  const start = Math.max(0, Math.min(text.length, range.start));
  const end = Math.max(start, Math.min(text.length, range.end));
  const normalizedSource = normalizeWithMap(text.slice(start, end));
  const normalizedCandidate = normalizeWithMap(candidate).value;
  if (!normalizedCandidate) return undefined;

  const found = normalizedSource.value.indexOf(normalizedCandidate);
  if (found < 0) return undefined;

  return {
    start: start + normalizedSource.sourceIndexes[found],
    end:
      start +
      normalizedSource.sourceIndexes[found + normalizedCandidate.length - 1] +
      1,
  };
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
  return candidates.filter((v, i, a) => v.trim().length > 0 && a.indexOf(v) === i);
}

function declaredEvidenceRanges(entity: EntityRecord): TextRange[] {
  const ranges: TextRange[] = [];
  const addRange = (start?: number, end?: number) => {
    if (
      typeof start === "number" &&
      typeof end === "number" &&
      start >= 0 &&
      end > start
    ) {
      ranges.push({ start, end });
    }
  };

  addRange(entity.evidence_span?.start, entity.evidence_span?.end);
  for (const span of entity.evidence_spans ?? []) {
    addRange(span.start, span.end);
  }
  return ranges;
}

function findEntityName(text: string, entity: EntityRecord): TextRange | undefined {
  if (!entity.name.trim()) return undefined;

  for (const range of declaredEvidenceRanges(entity)) {
    const match = findNormalizedMatch(text, entity.name, range);
    if (match) return match;
  }

  for (const evidence of evidenceCandidates(entity)) {
    const evidenceRange = findNormalizedMatch(text, evidence);
    if (!evidenceRange) continue;
    const match = findNormalizedMatch(text, entity.name, evidenceRange);
    if (match) return match;
  }

  return findNormalizedMatch(text, entity.name);
}

export function buildHighlightSegments(
  text: string,
  entities: EntityRecord[],
): HighlightSegment[] {
  const matches: Array<{ start: number; end: number; entity: EntityRecord }> = [];

  for (const entity of entities) {
    const best = findEntityName(text, entity);
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
