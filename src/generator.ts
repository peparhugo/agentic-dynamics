import fs from 'fs';
import path from 'path';
import { parseMarkdownWithYaml, type PageMetadata } from './parser.js';
import { TemplateEngine, createDefaultLayout, createDefaultIndexLayout, createDefaultNavPartial } from './template.js';

export interface PageData {
  slug: string;
  filename: string;
  content: string;
  metadata: PageMetadata;
}

export interface GeneratorOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  layoutsDir?: string;
  partialsDir?: string;
}

function slugFromFilename(filename: string): string {
  return filename.replace(/\.md$/, '');
}

function generatePageHtml(page: PageData, templateEngine: TemplateEngine | null): string {
  const title = page.metadata.title || page.slug;
  const layoutName = page.metadata.layout || 'default.hbs';

  if (!templateEngine) {
    const date = page.metadata.date ? `<p class="date">${page.metadata.date}</p>` : '';
    const tags = page.metadata.tags && page.metadata.tags.length > 0
      ? `<div class="tags">${page.metadata.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}</div>`
      : '';

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)}</title>
  <style>
    body { font-family: sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }
    a { color: #0066cc; }
    .date { color: #666; font-size: 0.9em; }
    .tags { margin: 10px 0; }
    .tag { display: inline-block; background: #f0f0f0; padding: 2px 8px; margin: 2px; border-radius: 3px; font-size: 0.9em; }
    nav { border-bottom: 1px solid #ddd; margin-bottom: 20px; padding-bottom: 10px; }
  </style>
</head>
<body>
  <nav>
    <a href="index.html">← Home</a>
  </nav>
  <article>
    <h1>${escapeHtml(title)}</h1>
    ${date}
    ${tags}
    <div class="content">
      ${page.content}
    </div>
  </article>
</body>
</html>`;
  }

  return templateEngine.renderWithLayout(page.content, layoutName, {
    title: title,
    date: page.metadata.date,
    tags: page.metadata.tags || [],
    slug: page.slug,
    ...page.metadata
  });
}

function generateIndexHtml(pages: PageData[], templateEngine: TemplateEngine | null): string {
  const sortedPages = pages.sort((a, b) => {
    const dateA = new Date(a.metadata.date || '').getTime();
    const dateB = new Date(b.metadata.date || '').getTime();
    return dateB - dateA;
  });

  if (!templateEngine) {
    const pageLinks = sortedPages
      .map(page => {
        const title = page.metadata.title || page.slug;
        const dateStr = page.metadata.date ? ` (${page.metadata.date})` : '';
        return `<li><a href="${page.slug}.html">${escapeHtml(title)}</a>${dateStr}</li>`;
      })
      .join('\n    ');

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Home</title>
  <style>
    body { font-family: sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }
    a { color: #0066cc; }
    li { margin: 8px 0; }
  </style>
</head>
<body>
  <h1>Pages</h1>
  <ul>
    ${pageLinks}
  </ul>
</body>
</html>`;
  }

  const pageList = sortedPages.map(page => ({
    title: page.metadata.title || page.slug,
    slug: page.slug,
    date: page.metadata.date
  }));

  return templateEngine.render('index.hbs', 'index.hbs', { pages: pageList });
}

function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, char => map[char]);
}

export async function generate(options: GeneratorOptions): Promise<void> {
  const { contentDir, outputDir } = options;
  const templatesDir = options.templatesDir || './templates';
  const layoutsDir = options.layoutsDir || './templates/layouts';
  const partialsDir = options.partialsDir || './templates/partials';

  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }

  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  let templateEngine: TemplateEngine | null = null;

  if (fs.existsSync(templatesDir)) {
    ensureDefaultTemplates(templatesDir, layoutsDir, partialsDir);
    templateEngine = new TemplateEngine({
      templatesDir,
      layoutsDir,
      partialsDir
    });
  }

  const files = fs.readdirSync(contentDir).filter(file => file.endsWith('.md'));

  if (files.length === 0) {
    throw new Error(`No markdown files found in ${contentDir}`);
  }

  const pages: PageData[] = [];

  for (const file of files) {
    const filePath = path.join(contentDir, file);
    const content = fs.readFileSync(filePath, 'utf-8');
    const parsed = await parseMarkdownWithYaml(content);

    const page: PageData = {
      slug: slugFromFilename(file),
      filename: file,
      content: parsed.content,
      metadata: parsed.metadata
    };

    pages.push(page);

    const pageHtml = generatePageHtml(page, templateEngine);
    const outputPath = path.join(outputDir, `${page.slug}.html`);
    fs.writeFileSync(outputPath, pageHtml, 'utf-8');
  }

  const indexHtml = generateIndexHtml(pages, templateEngine);
  const indexPath = path.join(outputDir, 'index.html');
  fs.writeFileSync(indexPath, indexHtml, 'utf-8');

  console.log(`Generated site with ${pages.length} page(s) in ${outputDir}`);
}

function ensureDefaultTemplates(templatesDir: string, layoutsDir: string, partialsDir: string): void {
  if (!fs.existsSync(templatesDir)) {
    fs.mkdirSync(templatesDir, { recursive: true });
  }
  if (!fs.existsSync(layoutsDir)) {
    fs.mkdirSync(layoutsDir, { recursive: true });
  }
  if (!fs.existsSync(partialsDir)) {
    fs.mkdirSync(partialsDir, { recursive: true });
  }

  const defaultLayoutPath = path.join(layoutsDir, 'default.hbs');
  if (!fs.existsSync(defaultLayoutPath)) {
    fs.writeFileSync(defaultLayoutPath, createDefaultLayout(), 'utf-8');
  }

  const indexLayoutPath = path.join(layoutsDir, 'index.hbs');
  if (!fs.existsSync(indexLayoutPath)) {
    fs.writeFileSync(indexLayoutPath, createDefaultIndexLayout(), 'utf-8');
  }

  const indexTemplatePath = path.join(templatesDir, 'index.hbs');
  if (!fs.existsSync(indexTemplatePath)) {
    fs.writeFileSync(indexTemplatePath, '{{{body}}}', 'utf-8');
  }

  const navPartialPath = path.join(partialsDir, 'nav.hbs');
  if (!fs.existsSync(navPartialPath)) {
    fs.writeFileSync(navPartialPath, createDefaultNavPartial(), 'utf-8');
  }
}
