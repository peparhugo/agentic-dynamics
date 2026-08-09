import fs from 'fs';
import path from 'path';
import { parseAllMarkdown } from './parser';
import { Renderer } from './renderer';
import { buildTagIndices } from './tags';
import { generateRSS } from './rss';
import { CLIOptions, Page } from './types';

export class Generator {
  private options: CLIOptions;
  private renderer!: Renderer;

  constructor(options: CLIOptions) {
    this.options = options;
  }

  generate(): void {
    const { source, templates, output, drafts } = this.options;

    this.renderer = new Renderer(templates);

    const pages = parseAllMarkdown(source, drafts);
    const publishedPages = pages.filter(p => !p.frontmatter.draft);

    const siteConfig: Record<string, unknown> = {};

    fs.mkdirSync(output, { recursive: true });

    for (const page of pages) {
      this.writePage(page, pages, siteConfig);
    }

    this.generateTagPages(publishedPages, pages, siteConfig);
    this.generateRSSFeed(publishedPages, siteConfig);
    this.copyStaticAssets();
  }

  private writePage(page: Page, allPages: Page[], siteConfig: Record<string, unknown>): void {
    const html = this.renderer.render(page, allPages, siteConfig);
    const relPath = page.url.replace(/^\//, '') || 'index.html';
    const outputPath = path.join(this.options.output, relPath);

    if (page.url === '/' || !path.extname(outputPath)) {
      const dirPath = page.url === '/' ? this.options.output : path.join(this.options.output, page.url);
      fs.mkdirSync(dirPath, { recursive: true });
      fs.writeFileSync(path.join(dirPath, 'index.html'), html);
      return;
    }

    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, html);
  }

  private generateTagPages(
    publishedPages: Page[],
    allPages: Page[],
    siteConfig: Record<string, unknown>
  ): void {
    const tagIndices = buildTagIndices(publishedPages);

    for (const { tag, pages } of tagIndices) {
      const html = this.renderer.renderTagPage(tag, pages, allPages, siteConfig);
      const outputDir = path.join(this.options.output, 'tags');
      fs.mkdirSync(outputDir, { recursive: true });
      fs.writeFileSync(path.join(outputDir, `${tag}.html`), html);
    }
  }

  private generateRSSFeed(publishedPages: Page[], siteConfig: Record<string, unknown>): void {
    if (!siteConfig.url) return;

    const config = {
      title: (siteConfig.title as string) || 'My Site',
      description: (siteConfig.description as string) || '',
      site_url: siteConfig.url as string,
    };

    const rss = generateRSS(publishedPages, config);
    fs.writeFileSync(path.join(this.options.output, 'feed.xml'), rss);
  }

  private copyStaticAssets(): void {
    const sourceDir = this.options.source;

    const copyDir = (dir: string) => {
      if (!fs.existsSync(dir)) return;
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const srcPath = path.join(dir, entry.name);
        const relativePath = path.relative(sourceDir, srcPath);
        const destPath = path.join(this.options.output, relativePath);

        if (entry.isDirectory()) {
          if (entry.name.startsWith('.') || entry.name.startsWith('_')) continue;
          fs.mkdirSync(destPath, { recursive: true });
          copyDir(srcPath);
        } else if (!entry.name.endsWith('.md')) {
          fs.mkdirSync(path.dirname(destPath), { recursive: true });
          fs.copyFileSync(srcPath, destPath);
        }
      }
    };

    copyDir(sourceDir);
  }
}
