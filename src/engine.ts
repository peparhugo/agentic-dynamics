import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { BuildContext, BuildOptions, BuildPage, Page, Plugin } from './plugin.js';

async function markdownFiles(directory: string, base = directory): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(absolutePath, base);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [path.relative(base, absolutePath)] : [];
  }));
  return files.flat().sort((left, right) => left.localeCompare(right));
}

function outputPathFor(relativePath: string): string {
  const parsed = path.parse(relativePath);
  return path.join(parsed.dir, `${parsed.name}.html`);
}

export class SsgEngine {
  private started = false;
  private buildCount = 0;
  private pages: BuildPage[] = [];
  readonly options: BuildContext['options'];

  constructor(options: BuildOptions, private readonly plugins: Plugin[]) {
    this.options = {
      contentDir: path.resolve(options.contentDir ?? 'content'),
      outputDir: path.resolve(options.outputDir ?? 'dist'),
      templatesDir: path.resolve(options.templatesDir ?? 'templates')
    };
  }

  private context(): BuildContext {
    return { options: this.options, pages: this.pages, initialBuild: this.buildCount === 0 };
  }

  async start(): Promise<void> {
    if (this.started) return;
    this.started = true;
    for (const plugin of this.plugins) await plugin.onStart?.(this.context());
  }

  async build(): Promise<Page[]> {
    await this.start();
    this.pages = [];
    const context = this.context();
    for (const plugin of this.plugins) await plugin.beforeBuild?.(context);
    const files = await markdownFiles(this.options.contentDir);
    this.pages.push(...await Promise.all(files.map(async (sourcePath): Promise<BuildPage> => {
      const outputPath = outputPathFor(sourcePath);
      return {
        title: path.parse(sourcePath).name,
        tags: [],
        sourcePath,
        outputPath,
        url: `/${outputPath.split(path.sep).join('/')}`,
        source: await fs.readFile(path.join(this.options.contentDir, sourcePath), 'utf8'),
        html: '',
        data: {}
      };
    })));
    const destinations = new Set<string>();
    for (const page of this.pages) {
      if (page.outputPath === 'index.html' || destinations.has(page.outputPath)) {
        throw new Error(`Output path collision: ${page.outputPath}`);
      }
      destinations.add(page.outputPath);
    }
    await fs.rm(this.options.outputDir, { recursive: true, force: true });
    await fs.mkdir(this.options.outputDir, { recursive: true });
    for (const page of this.pages) {
      for (const plugin of this.plugins) await plugin.onFile?.(page, context);
    }
    for (const plugin of this.plugins) await plugin.afterBuild?.(context);
    this.buildCount += 1;
    return this.pages.map(({ source: _source, html: _html, data: _data, template: _template, layout: _layout, ...page }) => page);
  }

  async end(): Promise<void> {
    if (!this.started) return;
    const context = this.context();
    for (const plugin of this.plugins) await plugin.onEnd?.(context);
    this.started = false;
  }
}
