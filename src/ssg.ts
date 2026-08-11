import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Page, SSGOptions, PageTemplateData } from './types';
import { TemplateEngine } from './template-engine';

function slugify(filename: string): string {
  const name = path.basename(filename, path.extname(filename));
  return name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
}

function readMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) {
    return [];
  }
  return fs.readdirSync(contentDir)
    .filter(f => f.endsWith('.md'))
    .map(f => path.join(contentDir, f));
}

function parsePage(filePath: string): Page {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);
  const html = marked.parse(content) as string;
  const slug = slugify(path.basename(filePath));
  return {
    frontmatter: {
      title: data.title || slug,
      date: data.date,
      tags: data.tags,
      template: data.template,
      layout: data.layout,
    },
    html,
    slug,
  };
}

function toTemplateData(page: Page): PageTemplateData {
  const { title, date, tags } = page.frontmatter;
  return {
    title,
    date,
    dateFormatted: date ? new Date(date).toLocaleDateString('en-US') : undefined,
    tags,
    tagsStr: tags && tags.length > 0 ? tags.join(', ') : undefined,
    content: page.html,
    slug: page.slug,
  };
}

export function build(options: SSGOptions): void {
  const { contentDir, outputDir, templateDir } = options;

  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const engine = new TemplateEngine(templateDir);

  const files = readMarkdownFiles(contentDir);
  const pages: Page[] = [];

  for (const file of files) {
    const page = parsePage(file);
    pages.push(page);

    const data = toTemplateData(page);
    const pageHTML = engine.renderPage(data, page.frontmatter.template, page.frontmatter.layout);
    const outPath = path.join(outputDir, `${page.slug}.html`);
    fs.writeFileSync(outPath, pageHTML, 'utf-8');
  }

  const indexData = {
    title: 'My Static Site',
    pages: pages.map(toTemplateData),
  };
  const indexHTML = engine.renderIndex(indexData);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHTML, 'utf-8');
}
