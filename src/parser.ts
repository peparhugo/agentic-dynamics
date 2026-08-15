import matter from 'gray-matter';

export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  [key: string]: unknown;
}

export interface ParsedDocument {
  data: Frontmatter;
  content: string;
}

function parseScalar(value: string): unknown {
  const trimmed = value.trim();
  if (!trimmed) return '';
  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) ||
      (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
    return trimmed.slice(1, -1);
  }
  if (trimmed === 'true') return true;
  if (trimmed === 'false') return false;
  if (trimmed === 'null') return null;
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    return trimmed.slice(1, -1).split(',').map((item) => String(parseScalar(item))
      .trim()).filter(Boolean);
  }
  return trimmed;
}

function parseYamlBlock(block: string): Frontmatter {
  const data: Frontmatter = {};
  let activeList: string | undefined;
  for (const line of block.split(/\r?\n/)) {
    if (!line.trim() || line.trimStart().startsWith('#')) continue;
    const listItem = line.match(/^\s+-\s+(.+)$/);
    if (listItem && activeList) {
      const current = data[activeList];
      data[activeList] = [...(Array.isArray(current) ? current : []), parseScalar(listItem[1]) as string];
      continue;
    }
    const entry = line.match(/^\s*([^:]+):\s*(.*)$/);
    if (!entry) continue;
    const key = entry[1].trim();
    data[key] = parseScalar(entry[2]);
    activeList = entry[2].trim() ? undefined : key;
  }
  return data;
}

export function parseMarkdown(source: string): ParsedDocument {
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*(?:\r?\n|$)/);
  // gray-matter still supplies delimiter removal and content extraction; the
  // parser is deliberately neutral because YAML is handled above.
  const parsed = matter(source, { parser: () => ({}) });
  return {
    data: { ...(match ? parseYamlBlock(match[1]) : {}), ...(parsed.data as Frontmatter) },
    content: parsed.content,
  };
}
