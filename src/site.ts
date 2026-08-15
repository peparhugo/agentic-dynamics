import fs from 'fs';
import path from 'path';

import { parseMarkdown } from './markdown';
import { TemplateEngine, PageContext } from './templates';
import { Post } from './types';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}

export interface BuildResult {
  posts: Post[];
  filesWritten: string[];
  outputDir: string;
}

function escapeHtml(value: string): string {
  return String(value).replace(/[&<>"']/g, (ch) => {
    switch (ch) {
      case '&':
        return '&amp;';
      case '<':
        return '&lt;';
      case '>':
        return '&gt;';
      case '"':
        return '&quot;';
      case "'":
        return '&#39;';
      default:
        return ch;
    }
  });
}

function listMarkdownFiles(dir: string): string[] {
  const files: string[] = [];
  if (!fs.existsSync(dir)) {
    return files;
  }
  for (const entry of fs.readdirSync(dir)) {
    const fullPath = path.join(dir, entry);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      files.push(...listMarkdownFiles(fullPath));
    } else if (stat.isFile() && /\.md$/i.test(entry)) {
      files.push(fullPath);
    }
  }
  return files;
}

function slugForFile(filePath: string, contentDir: string): string {
  const relative = path.relative(contentDir, filePath);
  const withoutExtension = relative.replace(/\.md$/i, '');
  return withoutExtension.split(path.sep).join('/');
}

function renderIndex(posts: Post[]): string {
  const items = posts
    .map((post) => {
      const href = `${post.slug}.html`;
      const title = escapeHtml(post.title || post.slug);
      const date = post.date
        ? `<time datetime="${escapeHtml(post.date)}">${escapeHtml(post.date)}</time>`
        : '';
      const tags = post.tags.length
        ? `<span class="tags">${post.tags.map(escapeHtml).join(', ')}</span>`
        : '';
      const meta = [date, tags].filter(Boolean).join(' ');
      return `<li><a href="${href}">${title}</a>${meta ? ` — ${meta}` : ''}</li>`;
    })
    .join('\n    ');

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Site Index</title>
</head>
<body>
  <header><h1>Site Index</h1></header>
  <main>
    <ul>
    ${items || '<li>(no pages)</li>'}
    </ul>
  </main>
</body>
</html>
`;
}

function renderPage(post: Post): string {
  const title = escapeHtml(post.title || post.slug);
  const date = post.date
    ? `<time datetime="${escapeHtml(post.date)}">${escapeHtml(post.date)}</time>`
    : '';
  const tags = post.tags.length
    ? `<p class="tags">Tags: ${post.tags.map(escapeHtml).join(', ')}</p>`
    : '';

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
</head>
<body>
  <header>
    <a href="index.html">← Index</a>
    <h1>${title}</h1>
    ${date ? `<p>${date}</p>` : ''}
    ${tags}
  </header>
  <main>
${post.html}
  </main>
</body>
</html>
`;
}

function postToContext(post: Post): PageContext {
  return {
    title: post.title,
    date: post.date,
    tags: post.tags,
    slug: post.slug,
    content: post.content,
    body: post.html,
  };
}

export function buildSite(options: BuildOptions): BuildResult {
  const { contentDir, outputDir } = options;
  const templatesDir = options.templatesDir ?? path.join(process.cwd(), 'templates');
  const engine = new TemplateEngine(templatesDir);
  const markdownFiles = listMarkdownFiles(contentDir);

  const posts: Post[] = markdownFiles.map((filePath) => {
    const source = fs.readFileSync(filePath, 'utf-8');
    const { meta, content, html } = parseMarkdown(source);
    return {
      slug: slugForFile(filePath, contentDir),
      title: meta.title || slugForFile(filePath, contentDir),
      date: meta.date,
      tags: meta.tags,
      template: meta.template,
      content,
      html,
    };
  });

  posts.sort((a, b) => {
    const dateA = a.date ? Date.parse(a.date) : NaN;
    const dateB = b.date ? Date.parse(b.date) : NaN;
    if (!Number.isNaN(dateA) && !Number.isNaN(dateB) && dateA !== dateB) {
      return dateB - dateA;
    }
    if (Number.isNaN(dateA) && !Number.isNaN(dateB)) {
      return 1;
    }
    if (!Number.isNaN(dateA) && Number.isNaN(dateB)) {
      return -1;
    }
    return a.title.localeCompare(b.title);
  });

  fs.mkdirSync(outputDir, { recursive: true });

  const filesWritten: string[] = [];

  const indexPath = path.join(outputDir, 'index.html');
  fs.writeFileSync(indexPath, renderIndex(posts));
  filesWritten.push(indexPath);

  for (const post of posts) {
    const pagePath = path.join(outputDir, `${post.slug}.html`);
    fs.mkdirSync(path.dirname(pagePath), { recursive: true });
    const rendered = engine.render(post.template, postToContext(post));
    fs.writeFileSync(pagePath, rendered ?? renderPage(post));
    filesWritten.push(pagePath);
  }

  return { posts, filesWritten, outputDir };
}
