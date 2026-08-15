import fs from 'fs';
import path from 'path';
import { Plugin, PluginContext } from '../plugin';
import { Page } from '../types';
import { readMarkdownFiles, buildPage, sortByDate, pageFromCache } from '../markdown';
import { hashString } from '../cache';

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  beforeBuild(context: PluginContext): void {
    const files = readMarkdownFiles(context.contentDir);
    const incremental = context.incremental === true && context.clean !== true;
    const pages: Page[] = [];

    for (const file of files) {
      const fullPath = path.join(context.contentDir, file);
      const slug = path.basename(file, path.extname(file));
      const raw = fs.readFileSync(fullPath, 'utf-8');
      const sourceHash = hashString(raw);

      const entry = incremental ? context.cache?.getEntry(slug) : undefined;
      if (entry && entry.sourceHash === sourceHash && entry.frontmatter) {
        const page = pageFromCache(slug, entry.frontmatter, entry.bodyHtml);
        page.sourcePath = fullPath;
        page.sourceHash = sourceHash;
        pages.push(page);
        continue;
      }

      const page = buildPage(slug, raw);
      page.sourcePath = fullPath;
      page.sourceHash = sourceHash;
      pages.push(page);
    }

    context.pages = sortByDate(pages);
  }

  onFile(page: Page, _context: PluginContext): Page {
    return page;
  }
}
