export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface ParsedMarkdown {
  frontmatter: Frontmatter;
  content: string;
}

function parseYamlValue(value: string): unknown {
  value = value.trim();

  if (value === 'true') return true;
  if (value === 'false') return false;
  if (value === 'null' || value === '') return null;

  if (!isNaN(Number(value))) return Number(value);

  if (value.startsWith('[') && value.endsWith(']')) {
    const arrayContent = value.slice(1, -1).trim();
    if (!arrayContent) return [];
    return arrayContent.split(',').map((item) => {
      const trimmed = item.trim();
      return trimmed.startsWith('"') && trimmed.endsWith('"')
        ? trimmed.slice(1, -1)
        : trimmed;
    });
  }

  if (value.startsWith('"') && value.endsWith('"')) {
    return value.slice(1, -1);
  }

  return value;
}

function parseYaml(yamlContent: string): Record<string, unknown> {
  const lines = yamlContent.split('\n');
  const result: Record<string, unknown> = {};

  for (const line of lines) {
    if (!line.trim() || line.trim().startsWith('#')) continue;

    const colonIndex = line.indexOf(':');
    if (colonIndex === -1) continue;

    const key = line.substring(0, colonIndex).trim();
    const value = line.substring(colonIndex + 1).trim();

    if (key) {
      result[key] = parseYamlValue(value);
    }
  }

  return result;
}

export function parseFrontmatter(markdown: string): ParsedMarkdown {
  const lines = markdown.split('\n');

  if (!lines[0]?.trim().startsWith('---')) {
    return {
      frontmatter: {},
      content: markdown,
    };
  }

  let endIndex = -1;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i]?.trim().startsWith('---')) {
      endIndex = i;
      break;
    }
  }

  if (endIndex === -1) {
    return {
      frontmatter: {},
      content: markdown,
    };
  }

  const yamlLines = lines.slice(1, endIndex);
  const yamlContent = yamlLines.join('\n');
  const content = lines.slice(endIndex + 1).join('\n').trim();

  const parsed = parseYaml(yamlContent);

  return {
    frontmatter: parsed as Frontmatter,
    content,
  };
}
