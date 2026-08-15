import fs from 'fs';
import path from 'path';
import { parseMarkdownWithYaml } from '../parser.js';
import { Plugin, PageData, BuildContext } from '../plugin.js';
import { CacheManager } from '../cache.js';

function slugFromFilename(filename: string): string {
  return filename.replace(/\.md$/, '');
}

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  constructor() {
    this.beforeBuild = this.beforeBuild.bind(this);
  }

  async beforeBuild(context: BuildContext): Promise<void> {
    const { contentDir, pages, cacheManager, incremental, layoutsDir = './templates/layouts' } = context;

    if (!fs.existsSync(contentDir)) {
      throw new Error(`Content directory not found: ${contentDir}`);
    }

    const files = fs.readdirSync(contentDir).filter(file => file.endsWith('.md'));

    if (files.length === 0) {
      throw new Error(`No markdown files found in ${contentDir}`);
    }

    for (const file of files) {
      const filePath = path.join(contentDir, file);
      const content = fs.readFileSync(filePath, 'utf-8');
      const parsed = await parseMarkdownWithYaml(content);

      const slug = slugFromFilename(file);

      if (incremental && cacheManager instanceof CacheManager) {
        const layoutName = parsed.metadata.layout || 'default.hbs';
        const layoutPath = path.join(layoutsDir, layoutName);

        if (!cacheManager.hasChanged(`${slug}.md`, content, layoutPath)) {
          context.pagesSkipped = (context.pagesSkipped || 0) + 1;
          continue;
        }
        cacheManager.updateEntry(`${slug}.md`, content, layoutPath);
      }

      const page: PageData = {
        slug,
        filename: file,
        content: parsed.content,
        metadata: parsed.metadata
      };

      pages.push(page);
    }
  }
}
