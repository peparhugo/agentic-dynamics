import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Plugin, BuildContext } from '../plugin';
import { Page } from '../types';
import { CacheManager } from '../cache';

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

function parseFrontmatterFromFile(filePath: string): { data: any; content: string } {
  const raw = fs.readFileSync(filePath, 'utf-8');
  return matter(raw);
}

function parsePage(filePath: string): Page {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);
  const html = marked.parse(content) as string;
  const slug = slugify(path.basename(filePath));
  const frontmatter = {
    title: data.title || slug,
    date: data.date,
    tags: data.tags,
    template: data.template,
    layout: data.layout,
  };
  return { frontmatter, html, slug };
}

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  beforeBuild(context: BuildContext): void {
    const { contentDir } = context.options;
    const cache: CacheManager | undefined = context.cache;
    const incremental: boolean = !!context.incremental;
    const templatesChanged: boolean = !!context.templatesChanged;

    const files = readMarkdownFiles(contentDir);

    if (!files.length) {
      return;
    }

    const manifest = cache ? cache.getManifest() : null;

    for (const file of files) {
      const slug = slugify(path.basename(file));
      const sourceHash = cache ? cache.computeFileHash(file) : '';
      const { data } = parseFrontmatterFromFile(file);
      const templateName = data.template || 'default';
      const layoutName = data.layout || 'default';

      if (incremental && cache && manifest) {
        if (!cache.isPageDirty(slug, sourceHash, templateName, layoutName, templatesChanged)) {
          const cachedPage = cache.getCachedPage(slug);
          if (cachedPage) {
            (cachedPage as any)._fromCache = true;
            context.pages.push(cachedPage);
            cache.setPageEntry(slug, sourceHash, templateName, layoutName);
            continue;
          }
        }
      }

      const page = parsePage(file);
      context.pages.push(page);

      if (incremental && cache) {
        cache.setCachedPage(slug, page);
        cache.setCachedFrontmatter(slug, page.frontmatter);
        cache.setPageEntry(slug, sourceHash, templateName, layoutName);
        cache.incrementBuilt();
      }
    }
  }
}
