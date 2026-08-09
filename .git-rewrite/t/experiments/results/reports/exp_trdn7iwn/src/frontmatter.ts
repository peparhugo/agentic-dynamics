import yaml from "js-yaml";

export interface Frontmatter {
  title: string;
  date: Date | null;
  tags: string[];
  draft: boolean;
  layout: string;
  /** Any additional user-defined keys pass through untouched. */
  [key: string]: unknown;
}

export interface ParsedDocument {
  frontmatter: Frontmatter;
  body: string;
}

const FM_DELIMITER = /^---\s*\r?\n/;

/**
 * Parse a Markdown document with optional YAML frontmatter delimited by `---`.
 * Missing/absent frontmatter yields sensible defaults.
 */
export function parseFrontmatter(source: string): ParsedDocument {
  let raw: Record<string, unknown> = {};
  let body = source;

  if (FM_DELIMITER.test(source)) {
    const end = source.indexOf("\n---", source.indexOf("\n"));
    if (end !== -1) {
      const yamlBlock = source.slice(source.indexOf("\n") + 1, end);
      const rest = source.slice(end + 4).replace(/^\s*\r?\n/, "");
      const loaded = yaml.load(yamlBlock);
      if (loaded !== null && typeof loaded === "object" && !Array.isArray(loaded)) {
        raw = loaded as Record<string, unknown>;
        body = rest;
      }
    }
  }

  return { frontmatter: normalize(raw), body };
}

function normalize(raw: Record<string, unknown>): Frontmatter {
  const { title, date, tags, draft, layout, ...extra } = raw;
  return {
    ...extra,
    title: typeof title === "string" ? title : "",
    date: coerceDate(date),
    tags: coerceTags(tags),
    draft: draft === true,
    layout: typeof layout === "string" ? layout : "default",
  };
}

function coerceDate(value: unknown): Date | null {
  if (value instanceof Date) return isNaN(value.getTime()) ? null : value;
  if (typeof value === "string" || typeof value === "number") {
    const d = new Date(value);
    return isNaN(d.getTime()) ? null : d;
  }
  return null;
}

function coerceTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String).map((t) => t.trim()).filter(Boolean);
  }
  if (typeof value === "string") {
    return value.split(",").map((t) => t.trim()).filter(Boolean);
  }
  return [];
}
