import matter from 'gray-matter';

export interface Frontmatter {
  title: string;
  date?: string;
  tags: string[];
}

export interface ParsedDocument {
  frontmatter: Frontmatter;
  content: string;
}

// gray-matter requires the opening `---` to be the very first bytes of the
// file, so we extract the block manually (allowing an optional BOM) and hand
// only the raw frontmatter to gray-matter for YAML parsing.
const FRONTMATTER_RE = /^\uFEFF?---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/;

function dateToString(value: unknown): string | undefined {
  if (typeof value === 'string') {
    return value;
  }
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value.toISOString().slice(0, 10);
  }
  return undefined;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .filter((v): v is string => typeof v === 'string')
      .map((v) => v.trim())
      .filter((v) => v.length > 0);
  }
  if (typeof value === 'string') {
    return value
      .split(',')
      .map((v) => v.trim())
      .filter((v) => v.length > 0);
  }
  return [];
}

export function extractFrontmatter(source: string): ParsedDocument {
  const match = FRONTMATTER_RE.exec(source);
  if (!match) {
    return { frontmatter: { title: '', tags: [] }, content: source };
  }

  const parsed = matter(match[0]);
  const raw = parsed.data as Record<string, unknown>;

  return {
    frontmatter: {
      title: typeof raw.title === 'string' ? raw.title : '',
      date: dateToString(raw.date),
      tags: normalizeTags(raw.tags),
    },
    content: source.slice(match[0].length),
  };
}
