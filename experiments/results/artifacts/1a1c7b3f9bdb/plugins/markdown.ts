import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import matter from 'gray-matter';
import { marked } from 'marked';
import type { Page } from '../src/generator';
import type { BuildContext, Plugin } from '../src/plugin';

export class MarkdownPlugin implements Plugin {
  onFile(page: Page, context: BuildContext): Page {
    const source = (page as Page & { source: string }).source;
    const sourceText = fs.readFileSync(source, 'utf8');
    const relative = path.relative(context.options.contentDir, source);
    const sourceHash = crypto.createHash('sha256').update(sourceText).digest('hex');
    const cached = context.cache.pages[relative];
    const parsed = cached?.sourceHash === sourceHash && cached.frontmatter
      ? cached.frontmatter
      : (() => { const value = matter(sourceText); return { data: value.data as Record<string, unknown>, content: value.content }; })();
    context.cache.pages[relative] = { sourceHash, templateHash: cached?.templateHash ?? context.cache.templateHash, output: cached?.output ?? '', frontmatter: parsed };
    const slug = relative.replace(/\.md$/i, '').split(path.sep).join('/');
    const title = typeof parsed.data.title === 'string' ? parsed.data.title : path.basename(slug);
    const rawTags = parsed.data.tags;
    const tags = Array.isArray(rawTags) ? rawTags.map(String) : typeof rawTags === 'string' ? rawTags.split(',').map((tag) => tag.trim()).filter(Boolean) : [];
    return {
      ...parsed.data,
      title,
      date: parsed.data.date == null ? undefined : String(parsed.data.date),
      tags,
      slug,
      html: marked.parse(parsed.content) as string,
      _sourceHash: sourceHash,
      _sourceRelative: relative,
      template: typeof parsed.data.template === 'string' ? parsed.data.template : undefined,
      layout: typeof parsed.data.layout === 'string' ? parsed.data.layout : undefined
    };
  }
}

export default MarkdownPlugin;
