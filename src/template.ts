import fs from 'fs/promises';
import path from 'path';
import Handlebars from 'handlebars';
import { computeHash } from './hash';
import { Page } from './types';

export const DEFAULT_TEMPLATE_NAME = 'default';
export const DEFAULT_LAYOUT_NAME = 'default';
export const DEFAULT_TEMPLATE_DIR = './templates';

const TEMPLATE_EXTENSIONS = new Set(['.hbs', '.handlebars']);

const DEFAULT_PAGE_TEMPLATE = `<h1>{{title}}</h1>
{{#if date}}<p class="page-date">{{date}}</p>{{/if}}
{{#if tags.length}}<ul class="page-tags">{{#each tags}}<li class="tag">{{this}}</li>{{/each}}</ul>{{/if}}
<div class="content">
{{{body}}}
</div>
`;

const DEFAULT_LAYOUT_TEMPLATE = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{title}}</title>
</head>
<body>
  <nav><a href="index.html">&larr; Home</a></nav>
  <article>
{{{body}}}
  </article>
</body>
</html>
`;

export function isTemplateFile(fileName: string): boolean {
  return TEMPLATE_EXTENSIONS.has(path.extname(fileName).toLowerCase());
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    return (await fs.stat(filePath)).isFile();
  } catch {
    return false;
  }
}

export async function templateDirExists(templateDir: string): Promise<boolean> {
  try {
    return (await fs.stat(templateDir)).isDirectory();
  } catch {
    return false;
  }
}

async function resolveTemplateSource(
  templateDir: string,
  name: string,
  subDir?: string
): Promise<string | undefined> {
  const base = subDir ? path.join(templateDir, subDir) : templateDir;
  for (const ext of TEMPLATE_EXTENSIONS) {
    const candidate = path.join(base, `${name}${ext}`);
    if (await fileExists(candidate)) {
      return fs.readFile(candidate, 'utf-8');
    }
  }
  return undefined;
}

export async function registerPartials(templateDir: string): Promise<void> {
  const partialsDir = path.join(templateDir, 'partials');
  let entries;
  try {
    entries = await fs.readdir(partialsDir, { withFileTypes: true });
  } catch {
    return;
  }
  entries.sort((a, b) => a.name.localeCompare(b.name));
  for (const entry of entries) {
    if (!entry.isFile() || !isTemplateFile(entry.name)) continue;
    const name = entry.name.slice(0, -path.extname(entry.name).length);
    const source = await fs.readFile(path.join(partialsDir, entry.name), 'utf-8');
    Handlebars.registerPartial(name, source);
  }
}

export interface PageTemplateContext {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  source: string;
  body: string;
  html: string;
  page: Page;
}

function pageContext(page: Page): PageTemplateContext {
  return {
    title: page.title,
    date: page.date,
    tags: page.tags,
    slug: page.slug,
    source: page.source,
    body: page.html,
    html: page.html,
    page,
  };
}

export async function renderPageTemplate(
  page: Page,
  templateDir: string
): Promise<string> {
  const name = page.template ?? DEFAULT_TEMPLATE_NAME;
  const source =
    (await resolveTemplateSource(templateDir, name)) ?? DEFAULT_PAGE_TEMPLATE;
  return Handlebars.compile(source)(pageContext(page));
}

export async function renderLayout(
  content: string,
  page: Page,
  templateDir: string
): Promise<string> {
  const name = page.layout ?? DEFAULT_LAYOUT_NAME;
  const source =
    (await resolveTemplateSource(templateDir, name, 'layouts')) ??
    DEFAULT_LAYOUT_TEMPLATE;
  return Handlebars.compile(source)({
    body: content,
    title: page.title,
    date: page.date,
    tags: page.tags,
    slug: page.slug,
    source: page.source,
    page,
  });
}

export async function renderPageWithTemplates(
  page: Page,
  templateDir: string
): Promise<string> {
  const content = await renderPageTemplate(page, templateDir);
  return renderLayout(content, page, templateDir);
}

export async function computePartialsFingerprint(
  templateDir: string
): Promise<string> {
  const partialsDir = path.join(templateDir, 'partials');
  let entries;
  try {
    entries = await fs.readdir(partialsDir, { withFileTypes: true });
  } catch {
    return 'no-partials';
  }
  const parts: string[] = [];
  entries.sort((a, b) => a.name.localeCompare(b.name));
  for (const entry of entries) {
    if (!entry.isFile() || !isTemplateFile(entry.name)) continue;
    const source = await fs.readFile(path.join(partialsDir, entry.name), 'utf-8');
    parts.push(`${entry.name}:${source}`);
  }
  return computeHash(parts.join('\n'));
}

export async function computeTemplateHash(
  templateDir: string,
  pageMeta?: { template?: string; layout?: string },
  partialsFingerprint?: string
): Promise<string> {
  const templateName = pageMeta?.template ?? DEFAULT_TEMPLATE_NAME;
  const layoutName = pageMeta?.layout ?? DEFAULT_LAYOUT_NAME;

  if (!(await templateDirExists(templateDir))) {
    return computeHash(`no-template-dir:${path.resolve(templateDir)}`);
  }

  const parts: string[] = [];
  parts.push(`dir:${path.resolve(templateDir)}`);
  const pageSource = await resolveTemplateSource(templateDir, templateName);
  parts.push(`page:${templateName}:${pageSource ?? '__DEFAULT_PAGE_TEMPLATE__'}`);
  const layoutSource = await resolveTemplateSource(
    templateDir,
    layoutName,
    'layouts'
  );
  parts.push(`layout:${layoutName}:${layoutSource ?? '__DEFAULT_LAYOUT_TEMPLATE__'}`);

  if (partialsFingerprint !== undefined) {
    parts.push(`partials:${partialsFingerprint}`);
  } else {
    parts.push(`partials:${await computePartialsFingerprint(templateDir)}`);
  }

  return computeHash(parts.join('\n'));
}
