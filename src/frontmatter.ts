import matter from 'gray-matter';
import type { ParsedMarkdown } from './types';

const DELIMITER = '---';
const BOM = '\uFEFF';
const FRONTMATTER_OPEN = /^---\s*([\w-]*)\s*$/;

function stripBom(text: string): string {
  return text.startsWith(BOM) ? text.slice(1) : text;
}

function isDelimiter(line: string): boolean {
  return line.trim() === DELIMITER;
}

/**
 * Extract the raw `---`-delimited block from a markdown string.
 * Supports `---`, `---yaml` and `---json` delimiters. Returns null when
 * no well-formed frontmatter block is present.
 */
function extractYamlBlock(markdown: string): string | null {
  const lines = stripBom(markdown).split(/\r?\n/);
  const open = FRONTMATTER_OPEN.exec(lines[0] ?? '');
  if (!open) {
    return null;
  }
  const delim = open[1] ? `${DELIMITER}${open[1]}` : DELIMITER;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim() === delim) {
      return lines.slice(1, i).join('\n');
    }
  }
  return null;
}

/**
 * Remove the `---`-delimited frontmatter block, mirroring gray-matter's
 * behaviour of keeping the blank line that follows the closing delimiter.
 */
function stripFrontmatter(markdown: string): string {
  const lines = stripBom(markdown).split(/\r?\n/);
  if (lines[0].trim() !== DELIMITER) {
    return markdown;
  }
  for (let i = 1; i < lines.length; i++) {
    if (isDelimiter(lines[i])) {
      return lines.slice(i + 1).join('\n');
    }
  }
  return markdown;
}

function parseYamlList(value: string): string[] {
  const inner = value.slice(1, -1);
  if (inner.trim() === '') {
    return [];
  }
  return inner
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
    .map((item) => {
      if (
        (item.startsWith('"') && item.endsWith('"')) ||
        (item.startsWith("'") && item.endsWith("'"))
      ) {
        return item.slice(1, -1);
      }
      return item;
    });
}

/**
 * A deliberately simple `key: value` splitter for YAML frontmatter.
 * Supports quoted strings, booleans, numbers and inline flow-style lists.
 * Anything more exotic is left untouched (the raw string is used).
 */
export function parseYamlBlock(text: string): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (line.length === 0 || line.startsWith('#')) {
      continue;
    }
    const colonIndex = line.indexOf(':');
    if (colonIndex <= 0) {
      continue;
    }
    const key = line.slice(0, colonIndex).trim();
    if (key.length === 0) {
      continue;
    }
    let value = line.slice(colonIndex + 1).trim();
    if (value.length === 0) {
      result[key] = '';
      continue;
    }
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      result[key] = value.slice(1, -1);
      continue;
    }
    if (value.startsWith('[') && value.endsWith(']')) {
      result[key] = parseYamlList(value);
      continue;
    }
    const lower = value.toLowerCase();
    if (lower === 'true') {
      result[key] = true;
      continue;
    }
    if (lower === 'false') {
      result[key] = false;
      continue;
    }
    if (/^-?\d+$/.test(value) || /^-?\d+\.\d+$/.test(value)) {
      result[key] = Number(value);
      continue;
    }
    result[key] = value;
  }
  return result;
}

/**
 * Parse the `---`-delimited frontmatter block with the simple YAML splitter.
 * JSON frontmatter (block starting with `{` or `[`) is delegated to gray-matter.
 */
function parseYamlFromMarkdown(markdown: string): Record<string, unknown> {
  const block = extractYamlBlock(markdown);
  if (block === null) {
    return {};
  }
  const trimmed = block.trim();
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    return {};
  }
  return parseYamlBlock(block);
}

/**
 * Parse markdown with frontmatter support.
 *
 * gray-matter handles stripping the frontmatter block and parsing JSON
 * frontmatter. YAML frontmatter is parsed by our own splitter and merged
 * on top of gray-matter's output, so YAML keys always win.
 */
export function parseFrontmatter(markdown: string): ParsedMarkdown {
  const normalized = stripBom(markdown);
  const yamlData = parseYamlFromMarkdown(normalized);
  const hasFrontmatter = extractYamlBlock(normalized) !== null;

  let data: Record<string, unknown> = yamlData;
  let content = normalized;
  try {
    const parsed = matter(normalized);
    if (parsed.data !== null && typeof parsed.data === 'object' && !Array.isArray(parsed.data)) {
      data = { ...(parsed.data as Record<string, unknown>), ...yamlData };
    }
    if (hasFrontmatter && typeof parsed.content === 'string') {
      content = parsed.content;
    }
  } catch {
    content = hasFrontmatter ? stripFrontmatter(normalized) : normalized;
  }
  return { data, content };
}
