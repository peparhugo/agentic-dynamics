import { ParsedFrontmatter } from './types';

const DELIMITER = '---';

/**
 * Extract a `---`-delimited YAML frontmatter block from the top of a file.
 * Returns the raw YAML string (without delimiters) or null when absent.
 */
export function extractFrontmatterBlock(raw: string): string | null {
  if (!raw.startsWith(DELIMITER)) {
    return null;
  }
  const firstLineEnd = raw.indexOf('\n');
  if (firstLineEnd === -1) {
    return null;
  }
  const secondDelimiter = raw.indexOf(DELIMITER, firstLineEnd + 1);
  if (secondDelimiter === -1) {
    return null;
  }
  const block = raw.slice(firstLineEnd + 1, secondDelimiter).replace(/\n$/, '');
  return block;
}

/**
 * Parse a `---`-delimited YAML frontmatter block.
 *
 * YAML frontmatter is unsupported by gray-matter out of the box, so we parse
 * the block ourselves with a simple `key: value` splitter. Scalars (strings,
 * numbers, booleans), dates, and simple comma-separated lists are supported.
 */
export function parseFrontmatter(raw: string): ParsedFrontmatter {
  const block = extractFrontmatterBlock(raw);
  if (block === null) {
    return {};
  }
  return parseYamlBlock(block);
}

/** Parse a plain `key: value` YAML block into a record. */
export function parseYamlBlock(block: string): ParsedFrontmatter {
  const data: ParsedFrontmatter = {};
  for (const rawLine of block.split('\n')) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) {
      continue;
    }
    const match = /^([A-Za-z0-9_.-]+)\s*:\s*(.*)$/.exec(line);
    if (!match) {
      continue;
    }
    const key = match[1];
    const value = parseYamlValue(match[2].trim());
    data[key] = value;
  }
  return data;
}

function parseYamlValue(raw: string): unknown {
  if (raw === '') {
    return '';
  }
  if (raw.startsWith('[') && raw.endsWith(']')) {
    const inner = raw.slice(1, -1);
    if (inner.trim() === '') {
      return [];
    }
    return inner
      .split(',')
      .map((item) => item.trim())
      .map(parseYamlValue);
  }
  if (raw.startsWith('"') && raw.endsWith('"')) {
    return raw.slice(1, -1);
  }
  if (raw.startsWith("'") && raw.endsWith("'")) {
    return raw.slice(1, -1);
  }
  if (raw.includes(',')) {
    return raw
      .split(',')
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
      .map(parseYamlValue);
  }
  if (raw === 'true') {
    return true;
  }
  if (raw === 'false') {
    return false;
  }
  if (/^\d+$/.test(raw)) {
    return parseInt(raw, 10);
  }
  if (/^\d+\.\d+$/.test(raw)) {
    return parseFloat(raw);
  }
  return raw;
}
