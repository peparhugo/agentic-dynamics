import matter from 'gray-matter';
import { marked } from 'marked';
import { PageMetadata } from './types';

const parsedMarkdownCache = new Map<string, { metadata: PageMetadata; html: string }>();

function parseYamlValue(value: string): string | string[] {
  const trimmed = value.trim();
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    return trimmed.slice(1, -1).split(',').map((item) => item.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
  }
  return trimmed.replace(/^['"]|['"]$/g, '');
}

/** Extract the limited YAML frontmatter format supported by this generator. */
function extractYamlFrontmatter(source: string): { data: Record<string, string | string[]>; content: string } {
  const match = source.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!match) {
    return { data: {}, content: source };
  }

  const data: Record<string, string | string[]> = {};
  for (const line of match[1].split(/\r?\n/)) {
    const separator = line.indexOf(':');
    if (separator > 0) {
      data[line.slice(0, separator).trim()] = parseYamlValue(line.slice(separator + 1));
    }
  }
  return { data, content: source.slice(match[0].length) };
}

export function parseMarkdown(source: string, fallbackTitle: string): { metadata: PageMetadata; html: string } {
  const cacheKey = `${fallbackTitle}\0${source}`;
  const cached = parsedMarkdownCache.get(cacheKey);
  if (cached) return { metadata: { ...cached.metadata, tags: [...cached.metadata.tags] }, html: cached.html };
  const yaml = extractYamlFrontmatter(source);
  // gray-matter remains responsible for its native JSON frontmatter format.
  const parsed = matter(yaml.content);
  const data = { ...parsed.data, ...yaml.data } as Record<string, unknown>;
  const rawTags = data.tags;
  const tags = Array.isArray(rawTags)
    ? rawTags.map(String)
    : typeof rawTags === 'string'
      ? rawTags.split(',').map((tag) => tag.trim()).filter(Boolean)
      : [];

  const result = {
    metadata: { ...data, title: typeof data.title === 'string' ? data.title : fallbackTitle, date: typeof data.date === 'string' ? data.date : undefined, tags },
    html: marked.parse(parsed.content)
  };
  parsedMarkdownCache.set(cacheKey, result);
  return { metadata: { ...result.metadata, tags: [...result.metadata.tags] }, html: result.html };
}
