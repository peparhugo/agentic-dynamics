import fs from 'fs';
import path from 'path';
import { parseFrontmatter, Frontmatter } from './frontmatter';
import { markdownToHtml } from './markdown';
import { TemplateEngine } from './templates';

export interface PageData {
  slug: string;
  filename: string;
  frontmatter: Frontmatter;
  content: string;
  html: string;
}

export async function readMarkdownFiles(contentDir: string): Promise<string[]> {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }

  const files = fs.readdirSync(contentDir);
  return files.filter((file) => file.endsWith('.md'));
}

export async function parseMarkdownFile(
  filePath: string
): Promise<PageData> {
  const content = fs.readFileSync(filePath, 'utf-8');
  const { frontmatter, content: markdown } = parseFrontmatter(content);
  const html = markdownToHtml(markdown);
  const filename = path.basename(filePath);
  const slug = filename.replace(/\.md$/, '');

  return {
    slug,
    filename,
    frontmatter,
    content: markdown,
    html,
  };
}

export async function generatePages(
  contentDir: string,
  outputDir: string,
  templateEngine?: TemplateEngine
): Promise<PageData[]> {
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const files = await readMarkdownFiles(contentDir);
  const pages: PageData[] = [];

  for (const file of files) {
    const filePath = path.join(contentDir, file);
    const pageData = await parseMarkdownFile(filePath);
    pages.push(pageData);

    const outputPath = path.join(outputDir, `${pageData.slug}.html`);
    const html = templateEngine
      ? generatePageHtmlWithTemplate(pageData, templateEngine)
      : generatePageHtml(pageData);
    fs.writeFileSync(outputPath, html, 'utf-8');
  }

  return pages;
}

export function generatePageHtml(page: PageData): string {
  const title = page.frontmatter.title || page.slug;
  const date = page.frontmatter.date ? `<p class="date">${page.frontmatter.date}</p>` : '';
  const tags =
    page.frontmatter.tags && Array.isArray(page.frontmatter.tags)
      ? `<div class="tags">${page.frontmatter.tags
          .map((tag) => `<span class="tag">${escapeHtml(String(tag))}</span>`)
          .join('')}</div>`
      : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }
    h1, h2, h3 { margin-top: 1.5em; }
    .date { color: #666; font-size: 0.9em; }
    .tags { margin: 10px 0; }
    .tag { display: inline-block; background: #f0f0f0; padding: 4px 8px; margin: 4px 4px 4px 0; border-radius: 4px; font-size: 0.85em; }
    a { color: #0066cc; }
  </style>
</head>
<body>
  <a href="index.html">← Back to Index</a>
  <article>
    <h1>${escapeHtml(title)}</h1>
    ${date}
    ${tags}
    <div class="content">
      ${page.html}
    </div>
  </article>
</body>
</html>`;
}

export function generateIndexHtml(pages: PageData[]): string {
  const sortedPages = pages.sort((a, b) => {
    const dateA = new Date(String(a.frontmatter.date) || 0).getTime();
    const dateB = new Date(String(b.frontmatter.date) || 0).getTime();
    return dateB - dateA;
  });

  const pagesList = sortedPages
    .map((page) => {
      const title = page.frontmatter.title || page.slug;
      const date = page.frontmatter.date ? ` — ${page.frontmatter.date}` : '';
      return `<li><a href="${page.slug}.html">${escapeHtml(title)}</a>${date}</li>`;
    })
    .join('\n    ');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Site Index</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }
    h1 { margin-bottom: 1.5em; }
    ul { list-style: none; padding: 0; }
    li { margin: 12px 0; }
    a { color: #0066cc; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <h1>Site Index</h1>
  <ul>
    ${pagesList}
  </ul>
</body>
</html>`;
}

export function generatePageHtmlWithTemplate(
  page: PageData,
  templateEngine: TemplateEngine
): string {
  const templateName = String(page.frontmatter.template || 'page');
  const layoutName = String(page.frontmatter.layout || 'default');

  const context = {
    title: page.frontmatter.title || page.slug,
    slug: page.slug,
    filename: page.filename,
    date: page.frontmatter.date,
    tags: page.frontmatter.tags,
    content: page.html,
    ...page.frontmatter,
  };

  const templateContent = templateEngine.renderTemplate(templateName, context);

  if (templateEngine.hasLayout(layoutName)) {
    return templateEngine.renderPageWithLayout(templateContent, layoutName, context);
  }

  return templateContent;
}

export async function build(
  contentDir: string = './content',
  outputDir: string = './dist',
  templatesDir: string = './templates'
): Promise<void> {
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  let templateEngine: TemplateEngine | undefined;
  if (fs.existsSync(templatesDir)) {
    templateEngine = new TemplateEngine({
      templatesDir,
      layoutsDir: path.join(templatesDir, 'layouts'),
      partialsDir: path.join(templatesDir, 'partials'),
    });
  }

  const pages = await generatePages(contentDir, outputDir, templateEngine);
  const indexHtml = generateIndexHtml(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml, 'utf-8');
}

function escapeHtml(text: string): string {
  const escapeMap: { [key: string]: string } = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  };
  return text.replace(/[&<>"']/g, (char) => escapeMap[char]);
}
