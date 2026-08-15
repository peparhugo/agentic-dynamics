import * as fs from 'fs';
import * as path from 'path';
import { BuildOptions, PageMetadata } from './types.js';
import { PluginManager } from './plugin-manager.js';
import { Plugin, PluginContext, FileContext } from './plugin.js';
import { MarkdownPlugin } from './plugins/markdown-plugin.js';
import { TemplatePlugin } from './plugins/template-plugin.js';
import { CacheManager } from './cache-manager.js';

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  totalTime: number;
  timeSaved: number;
}

export class SiteGenerator {
  private contentDir: string;
  private outputDir: string;
  private templatesDir: string;
  private pluginManager: PluginManager;
  private cacheManager: CacheManager;
  private incremental: boolean;
  private clean: boolean;
  private buildStats: BuildStats = {
    pagesBuilt: 0,
    pagesSkipped: 0,
    totalTime: 0,
    timeSaved: 0,
  };

  constructor(options: BuildOptions, plugins?: Plugin[]) {
    this.contentDir = options.contentDir;
    this.outputDir = options.outputDir;
    this.templatesDir = options.templatesDir || './templates';
    this.incremental = options.incremental || false;
    this.clean = options.clean || false;
    this.cacheManager = new CacheManager(this.outputDir);

    const defaultPlugins = [new MarkdownPlugin(), new TemplatePlugin()];
    const allPlugins = plugins ? [...defaultPlugins, ...plugins] : defaultPlugins;
    this.pluginManager = new PluginManager(allPlugins);
  }

  private ensureDir(dirPath: string): void {
    if (!fs.existsSync(dirPath)) {
      fs.mkdirSync(dirPath, { recursive: true });
    }
  }

  private getMarkdownFiles(): string[] {
    if (!fs.existsSync(this.contentDir)) {
      return [];
    }

    return fs
      .readdirSync(this.contentDir)
      .filter((file) => file.endsWith('.md'))
      .sort();
  }

  private generateIndexHtml(pages: PageMetadata[]): string {
    const pagesList = pages
      .map(
        (page) => `    <li>
      <a href="${this.escapeHtml(page.url)}">${this.escapeHtml(page.title)}</a>
      ${page.date ? `<span style="color: #666; margin-left: 10px;">${this.escapeHtml(page.date)}</span>` : ''}
      ${page.tags.length > 0 ? `<div style="margin-top: 5px;"><small>${page.tags.map((tag) => `<span style="display: inline-block; background: #eee; padding: 2px 8px; border-radius: 3px; margin-right: 5px;">${this.escapeHtml(tag)}</span>`).join('')}</small></div>` : ''}
    </li>`
      )
      .join('\n');

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Static Site</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      line-height: 1.6;
      max-width: 800px;
      margin: 0 auto;
      padding: 20px;
      color: #333;
    }
    h1 { margin-top: 0; }
    ul { list-style: none; padding: 0; }
    li {
      padding: 15px;
      border: 1px solid #eee;
      margin-bottom: 10px;
      border-radius: 5px;
    }
    li:hover { background: #f9f9f9; }
    a { color: #0066cc; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <h1>Pages</h1>
  ${pages.length > 0 ? `<ul>\n${pagesList}\n  </ul>` : '<p>No pages found.</p>'}
</body>
</html>`;
  }

  private escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  getPluginManager(): PluginManager {
    return this.pluginManager;
  }

  getCacheManager(): CacheManager {
    return this.cacheManager;
  }

  getBuildStats(): BuildStats {
    return this.buildStats;
  }

  async build(): Promise<void> {
    const startTime = Date.now();
    this.buildStats = {
      pagesBuilt: 0,
      pagesSkipped: 0,
      totalTime: 0,
      timeSaved: 0,
    };

    this.ensureDir(this.outputDir);

    if (this.clean) {
      this.cacheManager.clear();
      this.cacheManager.saveManifest();
    }

    const pluginContext: PluginContext = {
      contentDir: this.contentDir,
      outputDir: this.outputDir,
      templatesDir: this.templatesDir,
    };

    await this.pluginManager.onStart(pluginContext);
    await this.pluginManager.beforeBuild(pluginContext);

    const markdownFiles = this.getMarkdownFiles();
    const pages: PageMetadata[] = [];
    const cachedPages: PageMetadata[] = [];

    for (const file of markdownFiles) {
      const filePath = path.join(this.contentDir, file);
      const content = fs.readFileSync(filePath, 'utf-8');

      let shouldRebuild = true;
      if (this.incremental && !this.clean) {
        shouldRebuild = this.shouldRebuildFile(file, content);
      }

      const fileContext: FileContext = {
        filename: file,
        filePath,
        content,
      };

      if (shouldRebuild) {
        await this.pluginManager.onFile(pluginContext, fileContext);

        if (fileContext.html && fileContext.pageMetadata) {
          const outputPath = path.join(this.outputDir, fileContext.pageMetadata.url);
          fs.writeFileSync(outputPath, fileContext.html);
          pages.push(fileContext.pageMetadata);

          const templatePath = this.getTemplatePath(
            fileContext.pageMetadata.template,
            pluginContext.templatesDir
          );
          const layoutPath = this.getLayoutPath(
            fileContext.pageMetadata.layout,
            pluginContext.templatesDir
          );

          this.cacheManager.updateEntry(
            file,
            content,
            fileContext.html,
            templatePath,
            layoutPath,
            {
              title: fileContext.pageMetadata.title,
              date: fileContext.pageMetadata.date,
              tags: fileContext.pageMetadata.tags,
            }
          );
          this.buildStats.pagesBuilt++;
        }
      } else {
        this.buildStats.pagesSkipped++;
        const cacheEntry = this.cacheManager.getEntry(file);
        if (cacheEntry) {
          const pageMetadata = this.reconstructMetadata(file, cacheEntry);
          if (pageMetadata) {
            cachedPages.push(pageMetadata);
            pages.push(pageMetadata);
          }
        }
      }
    }

    const indexPath = path.join(this.outputDir, 'index.html');
    fs.writeFileSync(indexPath, this.generateIndexHtml(pages));

    this.cacheManager.saveManifest();

    await this.pluginManager.afterBuild(pluginContext, pages);
    await this.pluginManager.onEnd(pluginContext);

    this.buildStats.totalTime = Date.now() - startTime;
    this.reportBuildStats();
  }

  private shouldRebuildFile(filename: string, content: string): boolean {
    const template = this.getTemplateFromContent(content);
    const layout = this.getLayoutFromContent(content);

    const templatePath = template
      ? path.join(this.templatesDir, `${template}.hbs`)
      : undefined;
    const layoutPath = layout ? path.join(this.templatesDir, 'layouts', `${layout}.hbs`) : undefined;

    return this.cacheManager.isFileChanged(filename, content, templatePath, layoutPath);
  }

  private getTemplateFromContent(content: string): string | undefined {
    const match = content.match(/^---[\s\S]*?template:\s*(.+?)(?:\n|$)/m);
    return match ? match[1].trim() : undefined;
  }

  private getLayoutFromContent(content: string): string | undefined {
    const match = content.match(/^---[\s\S]*?layout:\s*(.+?)(?:\n|$)/m);
    return match ? match[1].trim() : undefined;
  }

  private getTemplatePath(template?: string, templatesDir?: string): string | undefined {
    if (!template || !templatesDir) return undefined;
    const templatePath = path.join(templatesDir, `${template}.hbs`);
    return fs.existsSync(templatePath) ? templatePath : undefined;
  }

  private getLayoutPath(layout?: string, templatesDir?: string): string | undefined {
    if (!layout || !templatesDir) return undefined;
    const layoutPath = path.join(templatesDir, 'layouts', `${layout}.hbs`);
    return fs.existsSync(layoutPath) ? layoutPath : undefined;
  }

  private reconstructMetadata(filename: string, cacheEntry: any): PageMetadata | null {
    return {
      filename,
      title: cacheEntry.title || filename.replace('.md', ''),
      date: cacheEntry.date,
      url: filename.replace('.md', '.html'),
      tags: cacheEntry.tags || [],
    };
  }

  private reportBuildStats(): void {
    const total = this.buildStats.pagesBuilt + this.buildStats.pagesSkipped;
    console.log(`✓ Generated ${total} page(s) to ${this.outputDir}`);

    if (this.incremental && this.buildStats.pagesSkipped > 0) {
      console.log(
        `  - Built: ${this.buildStats.pagesBuilt}, Skipped: ${this.buildStats.pagesSkipped}`
      );
      console.log(`  - Build time: ${this.buildStats.totalTime}ms`);
    }
  }
}
