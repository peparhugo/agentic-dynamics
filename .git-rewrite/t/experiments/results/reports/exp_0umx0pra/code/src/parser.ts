import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import hljs from 'highlight.js';
import { Frontmatter, PageData } from './types';

const renderer = new marked.Renderer();
renderer.code = (code: string, language: string | undefined, _isEscaped: boolean): string => {
  const lang = language && hljs.getLanguage(language) ? language : 'plaintext';
  const highlighted = hljs.highlight(code, { language: lang }).value;
  return `<pre><code class="hljs language-${lang}">${highlighted}</code></pre>\n`;
};

marked.setOptions({ renderer });

export function parseMarkdownFile(filePath: string, sourceDir: string): PageData {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);

  let dateStr: string | undefined;
  if (data.date) {
    if (data.date instanceof Date) {
      dateStr = data.date.toISOString().slice(0, 10);
    } else {
      dateStr = String(data.date);
    }
  }

  const frontmatter: Frontmatter = {
    title: data.title || path.basename(filePath, '.md'),
    date: dateStr,
    tags: normalizeTags(data.tags),
    draft: data.draft === true || data.draft === 'true',
    template: data.template,
    layout: data.layout,
  };

  for (const key of Object.keys(data)) {
    if (!['title', 'date', 'tags', 'draft', 'template', 'layout'].includes(key)) {
      (frontmatter as Record<string, unknown>)[key] = data[key];
    }
  }

  const html = marked.parse(content) as string;

  const relativePath = path.relative(sourceDir, filePath);
  const parsed = path.parse(relativePath);
  let slug = path.join(parsed.dir, parsed.name).replace(/\\/g, '/');
  if (slug.endsWith('/index')) {
    slug = slug.replace(/\/index$/, '');
  }
  const url = slug ? '/' + slug : '/';
  const outputPath = path.join(slug, 'index.html');

  return {
    frontmatter,
    markdown: content,
    html,
    sourcePath: filePath,
    relativePath,
    outputPath,
    url,
    slug,
    tags: (frontmatter.tags as string[]) || [],
    isDraft: frontmatter.draft === true,
  };
}

function normalizeTags(tags: unknown): string[] {
  if (!tags) return [];
  if (Array.isArray(tags)) return tags.map((t) => String(t));
  if (typeof tags === 'string') {
    return tags.split(',').map((t) => t.trim()).filter(Boolean);
  }
  return [];
}
