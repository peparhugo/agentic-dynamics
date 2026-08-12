import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import { Plugin } from '../types';

interface TemplateEnv {
  compiledTemplates: Record<string, Handlebars.TemplateDelegate>;
  compiledLayouts: Record<string, Handlebars.TemplateDelegate>;
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

function renderPage(pageHtml: string, templateName: string | undefined, layoutName: string | undefined, title: string, date: string | undefined, tags: string[] | undefined, tagsList: string, slug: string, env: TemplateEnv): string {
  const template = resolveTemplate(templateName, env.compiledTemplates, 'page');
  const layout = resolveLayout(layoutName, env.compiledLayouts, 'default');

  const context = {
    title,
    date: date || null,
    tags: tags || [],
    tagsList,
    content: pageHtml,
    slug,
  };

  const renderedContent = template(context);

  if (!layout) {
    return renderedContent;
  }

  return layout({
    title,
    body: renderedContent,
  });
}

function renderIndex(pages: Array<{ title: string; slug: string; date: string | null }>, env: TemplateEnv): string {
  const template = resolveTemplate(undefined, env.compiledTemplates, 'index');
  const layout = resolveLayout(undefined, env.compiledLayouts, 'default');

  const context = {
    title: 'My Site',
    pages,
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

export const TemplatePlugin: Plugin = {
  name: 'template',

  beforeBuild(ctx): void {
    const templatesDir = path.resolve(ctx.options.templatesDir || './templates');

    if (!fs.existsSync(templatesDir)) {
      throw new Error(`Templates directory not found: ${templatesDir}`);
    }

    const env = createTemplateEnv(templatesDir);
    ctx._templateEnv = env;

    ctx._renderIndex = function (pagesList: Array<{ title: string; slug: string; date: string | null }>): string {
      return renderIndex(pagesList, env);
    };

    ctx._renderPage = function (
      pageHtml: string,
      templateName: string | undefined,
      layoutName: string | undefined,
      title: string,
      date: string | undefined,
      tags: string[] | undefined,
      tagsList: string,
      slug: string,
    ): string {
      return renderPage(pageHtml, templateName, layoutName, title, date, tags, tagsList, slug, env);
    };
  },

  onFile(page, ctx): void {
    const templateName = page.frontmatter.template;
    const layoutName = page.frontmatter.layout;

    const tagsList = page.frontmatter.tags && page.frontmatter.tags.length > 0
      ? page.frontmatter.tags.join(', ')
      : '';

    page.html = ctx._renderPage(
      page.content,
      templateName,
      layoutName,
      page.frontmatter.title,
      page.frontmatter.date,
      page.frontmatter.tags,
      tagsList,
      page.slug,
    );
  },
};
