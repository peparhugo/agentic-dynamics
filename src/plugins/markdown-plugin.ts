import fs from 'fs';
import path from 'path';
import { renderMarkdownToHtml } from '../markdown';
import type { Page } from '../types';
import type { Plugin, PluginContext } from './types';

const MARKDOWN_EXTENSIONS = /\.(md|markdown)$/;

function pageTitle(data: Record<string, unknown>, slug: string): string {
  const title = data.title;
  return typeof title === 'string' && title.trim().length > 0 ? title : slug;
}

function pageDate(data: Record<string, unknown>): string | undefined {
  const date = data.date;
  return typeof date === 'string' && date.length > 0 ? date : undefined;
}

function pageTags(data: Record<string, unknown>): string[] | undefined {
  if (!Array.isArray(data.tags)) {
    return undefined;
  }
  const tags = data.tags.map(String).filter((tag) => tag.trim().length > 0);
  return tags.length > 0 ? tags : undefined;
}

function pageStringField(data: Record<string, unknown>, key: string): string | undefined {
  const value = data[key];
  return typeof value === 'string' && value.trim().length > 0 ? value : undefined;
}

/**
 * Built-in markdown plugin: reads `*.md` / `*.markdown` files from the
 * content directory, renders them to HTML and exposes the frontmatter as
 * page metadata. Files with any other extension are skipped.
 */
export class MarkdownPlugin implements Plugin {
  readonly name = 'markdown';

  onFile(page: Page, context: PluginContext): Page | undefined {
    const fileName = page.slug;
    if (!MARKDOWN_EXTENSIONS.test(fileName)) {
      return undefined;
    }
    const raw = fs.readFileSync(path.join(context.contentDir, fileName), 'utf8');
    const slug = fileName.replace(MARKDOWN_EXTENSIONS, '');
    const { data, content, html } = renderMarkdownToHtml(raw);
    return {
      slug,
      title: pageTitle(data, slug),
      date: pageDate(data),
      tags: pageTags(data),
      template: pageStringField(data, 'template'),
      layout: pageStringField(data, 'layout'),
      data,
      contentHtml: html,
      content,
    };
  }
}
