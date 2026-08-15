export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  [key: string]: unknown;
}

interface ParseResult {
  data: Frontmatter;
  content: string;
}

function parseYamlValue(value: string): unknown {
  const trimmed = value.trim();

  if (trimmed === 'true') return true;
  if (trimmed === 'false') return false;
  if (trimmed === 'null' || trimmed === '') return null;

  const num = Number(trimmed);
  if (!isNaN(num) && trimmed !== '') return num;

  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    const arrayStr = trimmed.slice(1, -1);
    return arrayStr.split(',').map((item) => item.trim());
  }

  return trimmed;
}

function parseYamlFrontmatter(yamlContent: string): Frontmatter {
  const data: Frontmatter = {};
  const lines = yamlContent.split('\n');

  for (const line of lines) {
    const colonIndex = line.indexOf(':');
    if (colonIndex === -1) continue;

    const key = line.substring(0, colonIndex).trim();
    const value = line.substring(colonIndex + 1).trim();

    data[key] = parseYamlValue(value);
  }

  return data;
}

export function parseFrontmatter(content: string): ParseResult {
  const lines = content.split('\n');

  if (lines[0] !== '---') {
    return {
      data: {},
      content,
    };
  }

  let endIndex = -1;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i] === '---') {
      endIndex = i;
      break;
    }
  }

  if (endIndex === -1) {
    return {
      data: {},
      content,
    };
  }

  const yamlContent = lines.slice(1, endIndex).join('\n');
  const markdownContent = lines.slice(endIndex + 1).join('\n');
  const data = parseYamlFrontmatter(yamlContent);

  return {
    data,
    content: markdownContent.trim(),
  };
}
