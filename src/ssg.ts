import * as fs from 'fs';
import * as path from 'path';
import { marked } from 'marked';
import { parseFrontmatter, type Frontmatter } from './frontmatter.js';
import { createTemplateEngine, renderIndexWithTemplate, renderEmptyIndex, type TemplateData } from './templates.js';

export interface PageMetadata {
  slug: string;
  title: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  metadata: PageMetadata;
  html: string;
}

function ensureDirectoryExists(dir: string): void {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function getMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) {
    return [];
  }

  const entries = fs.readdirSync(contentDir, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    if (entry.isFile() && entry.name.endsWith('.md')) {
      files.push(path.join(contentDir, entry.name));
    }
  }

  return files;
}

function slugify(filename: string): string {
  return filename.replace(/\.md$/, '').toLowerCase().replace(/[^a-z0-9]+/g, '-');
}

async function parseMarkdownFile(filePath: string): Promise<Page> {
  const content = fs.readFileSync(filePath, 'utf-8');
  const { data, content: markdown } = parseFrontmatter(content);
  const html = await marked(markdown);

  const filename = path.basename(filePath);
  const slug = slugify(filename);

  const metadata: PageMetadata = {
    slug,
    title: (data.title as string) || slug,
    ...(data.date && { date: data.date }),
    ...(data.tags && { tags: data.tags }),
    ...(data.template && { template: data.template as string }),
    ...(data.layout && { layout: data.layout as string }),
  };

  return {
    metadata,
    html,
  };
}

function renderPageTemplate(page: Page, templateEngine: ReturnType<typeof createTemplateEngine>): string {
  const { metadata, html } = page;
  const templateName = metadata.template || 'default';
  const layoutName = metadata.layout || 'default';

  const pageData: TemplateData = {
    title: metadata.title,
    slug: metadata.slug,
    body: html,
    ...(metadata.date && { date: metadata.date }),
    ...(metadata.tags && { tags: metadata.tags as string[] }),
  };

  const pageContent = templateEngine.renderPage(templateName, pageData);
  const layoutData: TemplateData = {
    title: metadata.title,
    slug: metadata.slug,
    body: pageContent,
  };

  return templateEngine.renderLayout(layoutName, layoutData);
}

export async function build(contentDir: string, outputDir: string, templatesDir: string = './templates'): Promise<void> {
  ensureDirectoryExists(outputDir);
  const templateEngine = createTemplateEngine(templatesDir);

  const markdownFiles = getMarkdownFiles(contentDir);

  if (markdownFiles.length === 0) {
    const indexHtml = renderEmptyIndex(templatesDir);
    fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml);
    return;
  }

  const pages = await Promise.all(markdownFiles.map((file) => parseMarkdownFile(file)));

  pages.forEach((page) => {
    const htmlContent = renderPageTemplate(page, templateEngine);
    const outputFile = path.join(outputDir, `${page.metadata.slug}.html`);
    fs.writeFileSync(outputFile, htmlContent);
  });

  const pageDataList: TemplateData[] = pages.map((page) => ({
    title: page.metadata.title,
    slug: page.metadata.slug,
    body: '',
    ...(page.metadata.date && { date: page.metadata.date }),
    ...(page.metadata.tags && { tags: page.metadata.tags as string[] }),
  }));

  const indexHtml = renderIndexWithTemplate(templatesDir, pageDataList);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml);
}
