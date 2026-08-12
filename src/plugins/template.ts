import fs from 'node:fs';
import path from 'node:path';
import { marked } from 'marked';
import type { Frontmatter, SitePage } from '../index';
import { renderTemplate } from '../template';
import type { MarkdownPage } from './markdown';
import type { Plugin, PluginContext } from '../plugin';

function templateName(name: string): string {
  return name.endsWith('.hbs') ? name : `${name}.hbs`;
}

function readTemplate(directory: string, name: string, kind: 'template' | 'layout'): string | undefined {
  const base = kind === 'layout' ? path.join(directory, 'layouts') : directory;
  const candidate = path.resolve(base, templateName(name));
  if (!candidate.startsWith(`${path.resolve(base)}${path.sep}`)) throw new Error(`Invalid ${kind} path: ${name}`);
  return fs.existsSync(candidate) ? fs.readFileSync(candidate, 'utf8') : undefined;
}

export class TemplatePlugin implements Plugin {
  onFile(page: SitePage, context: PluginContext): void {
    const markdownPage = page as MarkdownPage;
    const data = markdownPage.data ?? {} as Frontmatter;
    const body = marked.parse(markdownPage.markdown ?? '') as string;
    const template = page.template
      ? readTemplate(context.templatesDir, page.template, 'template')
      : readTemplate(context.templatesDir, 'default', 'template');
    if (page.template && template === undefined) throw new Error(`Template not found: ${page.template}`);
    const templateContext = { ...data, page, title: page.title, body, content: body };
    let result = template === undefined ? body : renderTemplate(template, templateContext, context.templatesDir);
    const layoutName = page.layout ?? (readTemplate(context.templatesDir, 'default', 'layout') !== undefined ? 'default' : undefined);
    if (layoutName) {
      const layout = readTemplate(context.templatesDir, layoutName, 'layout');
      if (layout === undefined) throw new Error(`Layout not found: ${layoutName}`);
      result = renderTemplate(layout, { ...templateContext, body: result, content: result }, context.templatesDir);
    }
    markdownPage.rendered = result;
  }
}
