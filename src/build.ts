import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import Handlebars from 'handlebars';
import { Page, BuildOptions, Frontmatter } from './types';

function readPages(contentDir: string): Page[] {
  const absDir = path.resolve(contentDir);
  if (!fs.existsSync(absDir)) {
    throw new Error(`Content directory not found: ${absDir}`);
  }

  const entries = fs.readdirSync(absDir, { withFileTypes: true });
  const pages: Page[] = [];

  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith('.md')) {
      continue;
    }

    const filePath = path.join(absDir, entry.name);
    const raw = fs.readFileSync(filePath, 'utf-8');
    const parsed = matter(raw);

    const slug = entry.name.replace(/\.md$/, '');
    const rawData = parsed.data as Record<string, unknown>;

    if (!rawData.title || typeof rawData.title !== 'string') {
      throw new Error(`Missing title in frontmatter for: ${entry.name}`);
    }

    let date: string | undefined;
    if (rawData.date instanceof Date) {
      date = rawData.date.toISOString().split('T')[0];
    } else if (typeof rawData.date === 'string') {
      date = rawData.date;
    }

    let tags: string[] | undefined;
    if (Array.isArray(rawData.tags)) {
      tags = rawData.tags.map((t) => String(t));
    }

    const frontmatter: Frontmatter = {
      title: rawData.title,
      date,
      tags,
    };

    if (rawData.template && typeof rawData.template === 'string') {
      frontmatter.template = rawData.template;
    }
    if (rawData.layout === false || rawData.layout === '') {
      frontmatter.layout = '';
    } else if (rawData.layout && typeof rawData.layout === 'string') {
      frontmatter.layout = rawData.layout;
    }

    pages.push({
      frontmatter,
      content: parsed.content,
      slug,
    });
  }

  pages.sort((a, b) => {
    if (a.frontmatter.date && b.frontmatter.date) {
      return new Date(b.frontmatter.date).getTime() - new Date(a.frontmatter.date).getTime();
    }
    if (a.frontmatter.date) return -1;
    if (b.frontmatter.date) return 1;
    return a.frontmatter.title.localeCompare(b.frontmatter.title);
  });

  return pages;
}

function loadPartial(partialsDir: string, name: string): void {
  const filePath = path.join(partialsDir, `${name}.hbs`);
  if (fs.existsSync(filePath)) {
    const content = fs.readFileSync(filePath, 'utf-8');
    Handlebars.registerPartial(name, content);
  }
}

function loadPartialDir(partialsDir: string): void {
  if (!fs.existsSync(partialsDir)) return;
  const entries = fs.readdirSync(partialsDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith('.hbs')) continue;
    const name = path.basename(entry.name, '.hbs');
    const content = fs.readFileSync(path.join(partialsDir, entry.name), 'utf-8');
    Handlebars.registerPartial(name, content);
  }
}

function compileFile(filePath: string): Handlebars.TemplateDelegate {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Template not found: ${filePath}`);
  }
  const content = fs.readFileSync(filePath, 'utf-8');
  return Handlebars.compile(content);
}

interface TemplateEnv {
  compiledTemplates: Record<string, Handlebars.TemplateDelegate>;
  compiledLayouts: Record<string, Handlebars.TemplateDelegate>;
}

function createTemplateEnv(templatesDir: string): TemplateEnv {
  Handlebars.registerPartial('nav', '');

  const partialsDir = path.join(templatesDir, 'partials');
  loadPartialDir(partialsDir);

  const layoutsDir = path.join(templatesDir, 'layouts');
  const compiledTemplates: Record<string, Handlebars.TemplateDelegate> = {};
  const compiledLayouts: Record<string, Handlebars.TemplateDelegate> = {};

  if (fs.existsSync(templatesDir)) {
    const entries = fs.readdirSync(templatesDir, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isFile() || !entry.name.endsWith('.hbs')) continue;
      const name = path.basename(entry.name, '.hbs');
      const content = fs.readFileSync(path.join(templatesDir, entry.name), 'utf-8');
      compiledTemplates[name] = Handlebars.compile(content);
    }
  }

  if (fs.existsSync(layoutsDir)) {
    const entries = fs.readdirSync(layoutsDir, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isFile() || !entry.name.endsWith('.hbs')) continue;
      const name = path.basename(entry.name, '.hbs');
      const content = fs.readFileSync(path.join(layoutsDir, entry.name), 'utf-8');
      compiledLayouts[name] = Handlebars.compile(content);
    }
  }

  return { compiledTemplates, compiledLayouts };
}

function resolveTemplate(
  templateName: string | undefined,
  compiledTemplates: Record<string, Handlebars.TemplateDelegate>,
  defaultName: string,
): Handlebars.TemplateDelegate {
  const name = templateName || defaultName;
  const tmpl = compiledTemplates[name];
  if (!tmpl) {
    throw new Error(`Template not found: ${name}`);
  }
  return tmpl;
}

function resolveLayout(
  layoutName: string | undefined,
  compiledLayouts: Record<string, Handlebars.TemplateDelegate>,
  defaultName: string,
): Handlebars.TemplateDelegate | null {
  if (layoutName === '') return null;
  const name = layoutName || defaultName;
  if (!compiledLayouts[name]) {
    if (layoutName) {
      throw new Error(`Layout not found: ${layoutName}`);
    }
    return null;
  }
  return compiledLayouts[name];
}

function renderPage(
  page: Page,
  env: TemplateEnv,
): string {
  const htmlContent = marked.parse(page.content, { async: false }) as string;

  const templateName = page.frontmatter.template || 'page';
  const layoutName = page.frontmatter.layout || 'default';

  const template = resolveTemplate(page.frontmatter.template, env.compiledTemplates, 'page');
  const layout = resolveLayout(page.frontmatter.layout, env.compiledLayouts, 'default');

  const tagsList = page.frontmatter.tags && page.frontmatter.tags.length > 0
    ? page.frontmatter.tags.join(', ')
    : '';

  const context = {
    title: page.frontmatter.title,
    date: page.frontmatter.date || null,
    tags: page.frontmatter.tags || [],
    tagsList,
    content: htmlContent,
    slug: page.slug,
  };

  const renderedContent = template(context);

  if (!layout) {
    return renderedContent;
  }

  return layout({
    title: page.frontmatter.title,
    body: renderedContent,
  });
}

function renderIndex(
  pages: Page[],
  env: TemplateEnv,
): string {
  const template = resolveTemplate(undefined, env.compiledTemplates, 'index');
  const layout = resolveLayout(undefined, env.compiledLayouts, 'default');

  const pagesData = pages.map((page) => ({
    title: page.frontmatter.title,
    slug: page.slug,
    date: page.frontmatter.date || null,
  }));

  const context = {
    title: 'My Site',
    pages: pagesData,
  };

  const renderedContent = template(context);

  if (!layout) {
    return renderedContent;
  }

  return layout({
    title: 'My Site',
    body: renderedContent,
  });
}

export function build(options: BuildOptions): void {
  const { contentDir, outputDir } = options;
  const templatesDir = path.resolve(options.templatesDir || './templates');

  if (!fs.existsSync(templatesDir)) {
    throw new Error(`Templates directory not found: ${templatesDir}`);
  }

  const pages = readPages(contentDir);
  const env = createTemplateEnv(templatesDir);

  const absOutputDir = path.resolve(outputDir);
  fs.mkdirSync(absOutputDir, { recursive: true });

  for (const page of pages) {
    const html = renderPage(page, env);
    const outPath = path.join(absOutputDir, `${page.slug}.html`);
    fs.writeFileSync(outPath, html, 'utf-8');
  }

  const indexHtml = renderIndex(pages, env);
  fs.writeFileSync(path.join(absOutputDir, 'index.html'), indexHtml, 'utf-8');
}
