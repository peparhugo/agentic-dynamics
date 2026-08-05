import yaml from "js-yaml";

export interface Frontmatter {
  title: string;
  date: Date | null;
  tags: string[];
  draft: boolean;
  layout: string;
  [key: string]: unknown;
}

export interface ParsedDocument {
  data: Frontmatter;
  content: string;
}

const FM_RE = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/;

function toDate(value: unknown): Date | null {
  if (value instanceof Date) return value;
  if (typeof value === "string" || typeof value === "number") {
    const d = new Date(value);
    if (!Number.isNaN(d.getTime())) return d;
  }
  return null;
}

function toTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === "string") {
    return value
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
  }
  return [];
}

/** Parse a Markdown document with optional YAML frontmatter delimited by `---`. */
export function parseFrontmatter(source: string): ParsedDocument {
  let raw: Record<string, unknown> = {};
  let content = source;

  const match = FM_RE.exec(source);
  if (match) {
    const parsed = yaml.load(match[1] ?? "");
    if (parsed !== null && typeof parsed === "object" && !Array.isArray(parsed)) {
      raw = parsed as Record<string, unknown>;
    } else if (parsed != null) {
      throw new Error("Frontmatter must be a YAML mapping");
    }
    content = source.slice(match[0].length);
  }

  const data: Frontmatter = {
    ...raw,
    title: typeof raw.title === "string" ? raw.title : "",
    date: toDate(raw.date),
    tags: toTags(raw.tags),
    draft: raw.draft === true,
    layout: typeof raw.layout === "string" ? raw.layout : "default",
  };

  return { data, content };
}
