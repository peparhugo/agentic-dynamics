/**
 * Frontmatter parsing.
 *
 * gray-matter only parses JSON frontmatter out of the box, so the
 * `---`-delimited YAML block is parsed here with a simple key: value
 * splitter and merged into gray-matter's output before the data is
 * passed on to the renderer.
 */

import matter from 'gray-matter';
import type { Frontmatter } from './types';

const DELIMITER_RE = /^---[ \t]*\r?\n([\s\S]*?)\r?\n[ \t]*---[ \t]*(?:\r?\n|$)/;

/**
 * Extract the raw YAML block (the text between the leading `---`
 * delimiters) from a Markdown source string, or null if there is no
 * frontmatter block.
 */
export function extractYamlBlock(source: string): string | null {
  const match = DELIMITER_RE.exec(source);
  return match ? match[1] : null;
}

/**
 * Coerce a single scalar string into a more useful typed value.
 * Handles quoted strings, numbers, booleans, inline arrays and
 * comma-separated lists (e.g. `tags: a, b`).
 */
export function coerceScalar(value: string): unknown {
  const trimmed = value.trim();

  // Inline array: [a, b, c]
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    return trimmed
      .slice(1, -1)
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
      .map((item) => stripQuotes(item));
  }

  // Strip surrounding single or double quotes
  const unquoted = stripQuotes(trimmed);

  if (unquoted === 'true') return true;
  if (unquoted === 'false') return false;
  if (/^-?\d+(\.\d+)?$/.test(unquoted)) return Number(unquoted);

  // Comma-separated list such as `tags: foo, bar`
  if (unquoted.includes(',')) {
    return unquoted.split(',').map((item) => item.trim()).filter(Boolean);
  }

  return unquoted;
}

function stripQuotes(value: string): string {
  if (value.length >= 2) {
    const first = value[0];
    const last = value[value.length - 1];
    if ((first === '"' && last === '"') || (first === "'" && last === "'")) {
      return value.slice(1, -1);
    }
  }
  return value;
}

/**
 * Parse a `---`-delimited YAML block into a plain object using a simple
 * `key: value` splitter. Supports:
 *  - scalar values: `key: value`
 *  - quoted values: `key: "value"`, `key: 'value'`
 *  - inline arrays: `tags: [a, b]`
 *  - comma separated lists: `tags: a, b`
 *  - block lists:  `tags:\n  - a\n  - b`
 */
export function parseYamlBlock(block: string): Record<string, unknown> {
  const data: Record<string, unknown> = {};

  let listKey: string | null = null;
  const listItems: string[] = [];

  for (const rawLine of block.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;

    const listMatch = line.match(/^-\s+(.*)$/);
    if (listMatch) {
      if (listKey) {
        listItems.push(stripQuotes(listMatch[1].trim()));
      }
      continue;
    }

    const separatorIndex = line.indexOf(':');
    if (separatorIndex === -1) continue;

    const key = line.slice(0, separatorIndex).trim();
    if (!key) continue;

    const rawValue = line.slice(separatorIndex + 1).trim();

    // If a previous list was being accumulated, finalize it first.
    if (listKey && listItems.length > 0) {
      data[listKey] = [...listItems];
    }
    listKey = null;
    listItems.length = 0;

    if (rawValue === '') {
      // Empty value: might be the header of a block list on the next lines.
      listKey = key;
      continue;
    }

    data[key] = coerceScalar(rawValue);
  }

  if (listKey && listItems.length > 0) {
    data[listKey] = [...listItems];
  }

  return data;
}

/**
 * Parse a Markdown source string into frontmatter data and body content.
 * gray-matter handles the delimiter + content splitting (and JSON
 * frontmatter), and the custom YAML parser output is merged on top so
 * that YAML frontmatter is fully supported.
 */
export function parseFrontmatter(source: string): {
  data: Frontmatter;
  content: string;
} {
  const parsed = matter(source);

  const block = extractYamlBlock(source);
  const yamlData = block ? parseYamlBlock(block) : {};

  const gmData = (parsed.data ?? {}) as Record<string, unknown>;
  const data: Record<string, unknown> = { ...gmData, ...yamlData };

  // Normalise tags into a string array regardless of the source format.
  if ('tags' in data) {
    data.tags = normalizeTags(data.tags);
  }

  return { data: data as Frontmatter, content: parsed.content };
}

/** Normalise a tags value (array, comma list, block list) into string[]. */
export function normalizeTags(tags: unknown): string[] {
  if (Array.isArray(tags)) {
    return tags.map((tag) => String(tag).trim()).filter(Boolean);
  }
  if (typeof tags === 'string') {
    return tags.split(',').map((tag) => tag.trim()).filter(Boolean);
  }
  return [];
}
