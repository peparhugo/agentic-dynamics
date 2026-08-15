import matter from 'gray-matter';
import { marked } from 'marked';
import { Page, parseYamlFrontmatter } from '../generator';
import { Plugin } from '../plugin';

type Frontmatter = Record<string, string | string[]>;

export function parsePage(source: string, sourcePath: string, contentDir: string, outputDir: string): Page {
  const yaml = parseYamlFrontmatter(source);
  const parsed = matter(yaml.content);
  const data = { ...parsed.data, ...yaml.data } as Frontmatter;
  const sourceRelative = sourcePath.slice(contentDir.length).replace(/^[/\\]+/, '');
  const slug = sourceRelative.replace(/\.md$/i, '').replace(/\\/g, '/');
  const outputPath = `${outputDir}/${sourceRelative.replace(/\.md$/i, '')}.html`;
  const title = typeof data.title === 'string' && data.title ? data.title : slug.split('/').at(-1) ?? 'Untitled';
  const tags = Array.isArray(data.tags) ? data.tags : typeof data.tags === 'string' ? data.tags.split(',').map((tag) => tag.trim()).filter(Boolean) : [];

  return { sourcePath, outputPath, slug, title, date: typeof data.date === 'string' ? data.date : undefined, tags, html: marked.parse(parsed.content), template: typeof data.template === 'string' ? data.template : undefined, layout: typeof data.layout === 'string' ? data.layout : undefined };
}

export const MarkdownPlugin: Plugin = {
  onFile(page, context) {
    const cached = context.parsedPages.get(page.sourcePath);
    if (cached) {
      Object.assign(page, cached);
      return;
    }
    Object.assign(page, parsePage(context.sources.get(page.sourcePath) ?? '', page.sourcePath, context.contentDir, context.outputDir));
  },
};
