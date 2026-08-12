import fs from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Page } from '../src/generator';
import type { BuildContext, Plugin } from '../src/plugin';

export class MarkdownPlugin implements Plugin {
  onFile(page: Page, context: BuildContext): Page {
    const parsed = matter(fs.readFileSync((page as Page & { source: string }).source, 'utf8'));
    const relative = path.relative(context.options.contentDir, (page as Page & { source: string }).source);
    const slug = relative.replace(/\.md$/i, '').split(path.sep).join('/');
    const title = typeof parsed.data.title === 'string' ? parsed.data.title : path.basename(slug);
    const rawTags = parsed.data.tags;
    const tags = Array.isArray(rawTags) ? rawTags.map(String) : typeof rawTags === 'string' ? rawTags.split(',').map((tag) => tag.trim()).filter(Boolean) : [];
    return {
      ...parsed.data,
      title,
      date: parsed.data.date instanceof Date ? parsed.data.date.toISOString() : parsed.data.date == null ? undefined : String(parsed.data.date),
      tags,
      slug,
      html: marked.parse(parsed.content) as string,
      template: typeof parsed.data.template === 'string' ? parsed.data.template : undefined,
      layout: typeof parsed.data.layout === 'string' ? parsed.data.layout : undefined
    };
  }
}

export default MarkdownPlugin;
