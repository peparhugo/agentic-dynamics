import { readFileSync, readdirSync, existsSync } from 'fs';
import { join, extname, basename } from 'path';
import Handlebars from 'handlebars';
import { Post, SiteConfig, TemplateData } from './types';

interface Templates {
  layout: Handlebars.TemplateDelegate | null;
  post: Handlebars.TemplateDelegate | null;
  index: Handlebars.TemplateDelegate | null;
  tag: Handlebars.TemplateDelegate | null;
  partials: Record<string, Handlebars.TemplateDelegate>;
}

export function loadTemplates(templatesDir: string): Templates {
  const partialsDir = join(templatesDir, 'partials');
  const templates: Templates = {
    layout: null,
    post: null,
    index: null,
    tag: null,
    partials: {},
  };

  if (existsSync(partialsDir)) {
    for (const f of readdirSync(partialsDir)) {
      if (extname(f) === '.hbs' || extname(f) === '.handlebars') {
        const name = basename(f, extname(f));
        const src = readFileSync(join(partialsDir, f), 'utf-8');
        Handlebars.registerPartial(name, src);
        templates.partials[name] = Handlebars.compile(src);
      }
    }
  }

  function load(name: string): Handlebars.TemplateDelegate | null {
    for (const ext of ['.hbs', '.handlebars']) {
      const p = join(templatesDir, name + ext);
      if (existsSync(p)) {
        const src = readFileSync(p, 'utf-8');
        return Handlebars.compile(src);
      }
    }
    return null;
  }

  templates.layout = load('layout');
  templates.post = load('post');
  templates.index = load('index');
  templates.tag = load('tag');

  return templates;
}

export function renderPage(
  templates: Templates,
  post: Post,
  config: SiteConfig,
  allPosts: Post[],
  isDev: boolean,
): string {
  const td: TemplateData = {
    site: { title: config.siteTitle, url: config.siteUrl },
    page: {
      title: post.frontmatter.title,
      date: post.frontmatter.date || '',
      tags: post.frontmatter.tags || [],
      content: post.html,
      slug: post.slug,
    },
    posts: [post],
  };

  const postTemplate = templates.post || templates.layout;
  if (!postTemplate) {
    throw new Error('No post or layout template found');
  }

  let body = postTemplate(td);

  if (templates.layout && postTemplate !== templates.layout) {
    body = templates.layout({
      ...td,
      page: { ...td.page, content: body },
    });
  }

  if (isDev) {
    body = injectReload(body);
  }

  return body;
}

export function renderIndex(
  templates: Templates,
  posts: Post[],
  config: SiteConfig,
  isDev: boolean,
): string {
  const template = templates.index || templates.layout;
  if (!template) {
    throw new Error('No index or layout template found');
  }

  const td: TemplateData = {
    site: { title: config.siteTitle, url: config.siteUrl },
    page: { title: 'Home', slug: 'index' },
    posts,
  };

  let body = template(td);

  if (templates.layout && template !== templates.layout) {
    body = templates.layout({
      ...td,
      page: { ...td.page, content: body },
    });
  }

  if (isDev) {
    body = injectReload(body);
  }

  return body;
}

export function renderTagPage(
  templates: Templates,
  tag: string,
  tagPosts: Post[],
  config: SiteConfig,
  isDev: boolean,
): string {
  const template = templates.tag || templates.index || templates.layout;
  if (!template) {
    throw new Error('No suitable template found for tag page');
  }

  const td: TemplateData = {
    site: { title: config.siteTitle, url: config.siteUrl },
    page: { title: `Tag: ${tag}`, slug: `tags/${tag}` },
    posts: tagPosts,
    currentTag: tag,
  };

  let body = template(td);

  if (templates.layout && template !== templates.layout) {
    body = templates.layout({
      ...td,
      page: { ...td.page, content: body },
    });
  }

  if (isDev) {
    body = injectReload(body);
  }

  return body;
}

const RELOAD_SCRIPT =
  '<script>(()=>{var s=new WebSocket("ws://"+location.host+"/__ssg_reload");s.onmessage=()=>location.reload();})()</script>';

function injectReload(html: string): string {
  return html.replace('</body>', `${RELOAD_SCRIPT}</body>`);
}
