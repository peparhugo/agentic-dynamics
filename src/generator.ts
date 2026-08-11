import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import MarkdownIt from 'markdown-it';

export interface PageData {
  title: string;
  date: string;
  tags: string[];
  content: string;
  html: string;
  slug: string;
}

const md = new MarkdownIt();

function parseMarkdownFile(filePath: string): PageData | null {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const parsed = matter(raw);

  const title = String(parsed.data.title || 'Untitled');
  const rawDate = parsed.data.date;
  const date = rawDate instanceof Date ? rawDate.toISOString().slice(0, 10) : String(rawDate || '');
  const tags = Array.isArray(parsed.data.tags)
    ? parsed.data.tags.map((t: unknown) => String(t))
    : [];
  const content = parsed.content;
  const html = md.render(content);

  const slug = path.basename(filePath, path.extname(filePath));

  return { title, date, tags, content, html, slug };
}

function generatePageHtml(page: PageData): string {
  const tagsHtml = page.tags.map((t: string) => `<span class="tag">${t}</span>`).join(' ');
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(page.title)}</title>
  <style>
    body { font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }
    .tag { background: #e0e0e0; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.85rem; margin-right: 0.5rem; }
    .date { color: #666; font-size: 0.9rem; }
    nav a { margin-right: 1rem; }
  </style>
</head>
<body>
  <nav><a href="index.html">Home</a></nav>
  <h1>${escapeHtml(page.title)}</h1>
  <p class="date">${escapeHtml(page.date)}</p>
  <div class="tags">${tagsHtml}</div>
  <article>${page.html}</article>
</body>
</html>`;
}

function generateIndexHtml(pages: PageData[]): string {
  const items = pages
    .map(
      (p) => `
    <li>
      <a href="${escapeHtml(p.slug)}.html">${escapeHtml(p.title)}</a>
      <span class="date">${escapeHtml(p.date)}</span>
    </li>`
    )
    .join('');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Site Index</title>
  <style>
    body { font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }
    .date { color: #666; font-size: 0.9rem; margin-left: 1rem; }
    li { margin-bottom: 0.5rem; }
  </style>
</head>
<body>
  <h1>All Pages</h1>
  <ul>${items}
  </ul>
</body>
</html>`;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export function buildSite(contentDir: string, outputDir: string): void {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory does not exist: ${contentDir}`);
  }

  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const files = fs.readdirSync(contentDir).filter((f) => f.endsWith('.md'));

  const pages: PageData[] = [];
  for (const file of files) {
    const filePath = path.join(contentDir, file);
    const page = parseMarkdownFile(filePath);
    if (page) {
      pages.push(page);
    }
  }

  pages.sort((a, b) => b.date.localeCompare(a.date));

  for (const page of pages) {
    const html = generatePageHtml(page);
    const outPath = path.join(outputDir, `${page.slug}.html`);
    fs.writeFileSync(outPath, html, 'utf-8');
  }

  const indexHtml = generateIndexHtml(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml, 'utf-8');
}
