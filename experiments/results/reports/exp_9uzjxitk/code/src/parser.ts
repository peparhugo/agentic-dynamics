import fs from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import hljs from 'highlight.js';
import type { Frontmatter, Post } from './types.js';

const codeRenderer = {
  code(this: { text: string; lang?: string }): string {
    const lang = this.lang || '';
    const language = hljs.getLanguage(lang) ? lang : 'plaintext';
    const highlighted = hljs.highlight(this.text || '', { language }).value;
    return `<pre><code class="hljs language-${language}">${highlighted}</code></pre>`;
  },
};

marked.use({ renderer: codeRenderer });

export interface ParseResult {
  frontmatter: Frontmatter;
  raw: string;
  html: string;
}

const DEFAULT_FRONTMATTER: Frontmatter = {
  title: 'Untitled',
  date: new Date().toISOString().split('T')[0],
  tags: [],
  draft: false,
  layout: 'default',
};

export function parse(filePath: string): ParseResult {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);

  const frontmatter: Frontmatter = {
    ...DEFAULT_FRONTMATTER,
    ...data,
    tags: Array.isArray(data.tags) ? data.tags : typeof data.tags === 'string' ? data.tags.split(',').map((t: string) => t.trim()) : [],
    draft: Boolean(data.draft),
  };

  const html = marked.parse(content) as string;

  return { frontmatter, raw: content, html };
}

export function parseAll(srcDir: string): Post[] {
  const files = collectMarkdownFiles(srcDir);

  return files
    .map((filePath) => {
      const relative = path.relative(srcDir, filePath);
      const slug = relative.replace(/\.md$/, '').replace(/\\/g, '/');
      const parsed = parse(filePath);
      return { slug, ...parsed, body: '' };
    })
    .sort((a, b) => new Date(b.frontmatter.date).getTime() - new Date(a.frontmatter.date).getTime());
}

function collectMarkdownFiles(dir: string): string[] {
  const results: string[] = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectMarkdownFiles(full));
    } else if (entry.isFile() && entry.name.endsWith('.md')) {
      results.push(full);
    }
  }

  return results;
}
