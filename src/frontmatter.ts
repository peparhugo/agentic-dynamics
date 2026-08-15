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

/**
 * gray-matter only parses JSON frontmatter out of the box, so the raw
 * `---`-delimited YAML block is extracted here and parsed with a simple
 * key: value splitter, then merged on top of gray-matter's own output.
 */
export function parseFrontmatter(raw: string): ParsedMarkdown {
  const gm = matter(raw);
  const { block } = extractFrontmatterBlock(raw);
  const yamlData = parseSimpleYaml(block);
  const data: FrontmatterData = { ...gm.data, ...yamlData };

  if (typeof data.tags === 'string') {
    data.tags = splitList(data.tags);
  }

  return { data, content: gm.content };
}

function extractFrontmatterBlock(raw: string): { block: string; content: string } {
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!match) {
    return { block: '', content: raw };
  }
  return { block: match[1], content: match[2] };
}

function parseSimpleYaml(block: string): Record<string, unknown> {
  const data: Record<string, unknown> = {};
  const lines = block.split(/\r?\n/);

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;

    const separatorIndex = trimmed.indexOf(':');
    if (separatorIndex === -1) continue;

    const key = trimmed.slice(0, separatorIndex).trim();
    const rawValue = trimmed.slice(separatorIndex + 1).trim();
    if (!key) continue;

    data[key] = parseValue(rawValue);
  }

  return data;
}

function parseValue(value: string): unknown {
  if (value.startsWith('[') && value.endsWith(']')) {
    return splitList(value.slice(1, -1));
  }
  return stripQuotes(value);
}

function splitList(value: string): string[] {
  return value
    .split(',')
    .map((item) => stripQuotes(item.trim()))
    .filter((item) => item.length > 0);
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
