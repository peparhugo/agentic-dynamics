import matter from 'gray-matter';

export interface FrontmatterData {
  title?: string;
  date?: string;
  tags?: string[];
  [key: string]: unknown;
}

export interface ParsedMarkdown {
  data: FrontmatterData;
  content: string;
}

const FRONTMATTER_BLOCK = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/;

/**
 * Parses a single `key: value` line from a YAML-ish frontmatter block.
 * Supports quoted strings, bracketed arrays (`[a, b, c]`) and bare scalars.
 */
function parseValue(raw: string): unknown {
  const value = raw.trim();

  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }

  if (value.startsWith('[') && value.endsWith(']')) {
    const inner = value.slice(1, -1).trim();
    if (inner === '') return [];
    return inner.split(',').map((item) => stripQuotes(item.trim()));
  }

  return value;
}

function stripQuotes(value: string): string {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

/**
 * gray-matter only parses JSON frontmatter out of the box, so YAML blocks
 * (the format used throughout this project) must be split out manually
 * with a simple `key: value` line parser and merged into gray-matter's
 * output afterwards.
 */
export function parseYamlFrontmatter(block: string): FrontmatterData {
  const data: FrontmatterData = {};
  const lines = block.split(/\r?\n/);

  for (const line of lines) {
    if (!line.trim() || line.trim().startsWith('#')) continue;

    const separatorIndex = line.indexOf(':');
    if (separatorIndex === -1) continue;

    const key = line.slice(0, separatorIndex).trim();
    const rawValue = line.slice(separatorIndex + 1).trim();
    if (!key) continue;

    if (key === 'tags') {
      if (rawValue.startsWith('[')) {
        data.tags = parseValue(rawValue) as string[];
      } else if (rawValue === '') {
        data.tags = [];
      } else {
        data.tags = rawValue.split(',').map((tag) => stripQuotes(tag.trim())).filter(Boolean);
      }
    } else {
      data[key] = parseValue(rawValue);
    }
  }

  return data;
}

export function parseMarkdownFile(raw: string): ParsedMarkdown {
  let content = raw;
  let grayMatterData: Record<string, unknown> = {};

  try {
    const parsed = matter(raw);
    content = parsed.content;
    grayMatterData = parsed.data || {};
  } catch {
    // gray-matter cannot parse YAML frontmatter out of the box; fall back
    // to manually stripping the block below.
  }

  const match = FRONTMATTER_BLOCK.exec(raw);
  let yamlData: FrontmatterData = {};
  if (match) {
    yamlData = parseYamlFrontmatter(match[1]);
    content = raw.slice(match[0].length);
  }

  const data: FrontmatterData = { ...grayMatterData, ...yamlData };

  return { data, content: content.trim() };
}
