import matter from 'gray-matter';

export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[] | string;
}

const FRONTMATTER_RE = /^\uFEFF?---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(\r?\n|$)/;

export interface ParsedMarkdown {
  data: Frontmatter;
  body: string;
}

function normalizeDate(value: unknown): string | undefined {
  if (value == null) {
    return undefined;
  }
  if (value instanceof Date) {
    return value.toISOString().slice(0, 10);
  }
  return String(value);
}

/**
 * Strips the leading YAML frontmatter block (delimited by `---`) using a
 * regex, then parses the YAML with gray-matter. Stripping manually before
 * handing the body to `marked` is required: otherwise `marked` renders the
 * `---` delimiter block as literal HTML text.
 */
export function parseFrontmatter(raw: string): ParsedMarkdown {
  const match = FRONTMATTER_RE.exec(raw);
  if (!match) {
    return { data: {}, body: raw };
  }

  const yaml = match[1];
  const body = raw.slice(match[0].length);

  const parsed = matter(`---\n${yaml}\n---\n`);
  const data = parsed.data ?? {};
  return {
    data: {
      title: data.title,
      date: normalizeDate(data.date),
      tags: data.tags,
    },
    body,
  };
}

export function normalizeTags(tags: Frontmatter['tags']): string[] {
  if (tags == null) {
    return [];
  }
  if (Array.isArray(tags)) {
    return tags.map((t) => String(t).trim()).filter(Boolean);
  }
  if (typeof tags === 'string') {
    return tags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);
  }
  return [];
}
