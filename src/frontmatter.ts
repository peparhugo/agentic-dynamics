import matter from 'gray-matter';

export interface FrontmatterResult {
  data: Record<string, unknown>;
  content: string;
}

const FRONTMATTER_BLOCK = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/;

function parseScalar(raw: string): unknown {
  const trimmed = raw.trim();
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1);
  }
  if (trimmed === 'true') return true;
  if (trimmed === 'false') return false;
  if (trimmed !== '' && !Number.isNaN(Number(trimmed))) return Number(trimmed);
  return trimmed;
}

function parseValue(key: string, raw: string): unknown {
  const trimmed = raw.trim();
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    const inner = trimmed.slice(1, -1).trim();
    if (!inner) return [];
    return inner.split(',').map((item) => parseScalar(item));
  }
  if (key === 'tags' && trimmed.includes(',')) {
    return trimmed.split(',').map((item) => parseScalar(item));
  }
  return parseScalar(trimmed);
}

/**
 * Splits a `---`-delimited YAML frontmatter block into key: value pairs.
 * Only flat scalar/array values are supported (no nested maps).
 */
function parseSimpleYaml(block: string): Record<string, unknown> {
  const data: Record<string, unknown> = {};
  for (const line of block.split(/\r?\n/)) {
    const trimmedLine = line.trim();
    if (!trimmedLine || trimmedLine.startsWith('#')) continue;
    const separatorIndex = trimmedLine.indexOf(':');
    if (separatorIndex === -1) continue;
    const key = trimmedLine.slice(0, separatorIndex).trim();
    const rawValue = trimmedLine.slice(separatorIndex + 1);
    if (!key) continue;
    data[key] = parseValue(key, rawValue);
  }
  return data;
}

/**
 * Parses frontmatter from raw Markdown source. gray-matter only understands
 * JSON frontmatter here, so the `---`-delimited YAML block is additionally
 * parsed by hand and merged over gray-matter's output.
 */
export function parseFrontmatter(raw: string): FrontmatterResult {
  const parsed = matter(raw);
  const match = raw.match(FRONTMATTER_BLOCK);
  const yamlData = match ? parseSimpleYaml(match[1]) : {};
  return {
    data: { ...parsed.data, ...yamlData },
    content: parsed.content,
  };
}
