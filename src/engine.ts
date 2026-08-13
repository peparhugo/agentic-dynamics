import { promises as fs } from 'node:fs';
import path from 'node:path';
import { loadPlugins } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { BuildOptions, Page, Plugin, PluginContext, PluginPage } from './plugin';

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const location = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(location);
    return /\.md$/i.test(entry.name) ? [location] : [];
  }));
  return files.flat().sort();
}

export class SsgEngine {
  readonly options: PluginContext['options'];
  private plugins: Plugin[] = [];
  private pages: PluginPage[] = [];
  private started = false;

  constructor(private readonly buildOptions: BuildOptions = {}, private readonly additionalPlugins: Plugin[] = []) {
    this.options = {
      contentDir: path.resolve(buildOptions.contentDir ?? './content'),
      outputDir: path.resolve(buildOptions.outputDir ?? './dist'),
      templatesDir: path.resolve(buildOptions.templatesDir ?? './templates')
    };
  }

  private context(): PluginContext {
    return { options: this.options, pages: this.pages, build: () => this.build() };
  }

  async start(): Promise<void> {
    if (this.started) return;
    const configured = await loadPlugins(this.buildOptions);
    this.plugins = [new MarkdownPlugin(), ...configured, new TemplatePlugin(), ...this.additionalPlugins];
    this.started = true;
    for (const plugin of this.plugins) await plugin.onStart?.(this.context());
  }

  async build(): Promise<Page[]> {
    await this.start();
    this.pages = [];
    for (const plugin of this.plugins) await plugin.beforeBuild?.(this.context());
    const files = await markdownFiles(this.options.contentDir);
    await fs.rm(this.options.outputDir, { recursive: true, force: true });
    await fs.mkdir(this.options.outputDir, { recursive: true });

    for (const file of files) {
      const relative = path.relative(this.options.contentDir, file).replace(/\.md$/i, '.html');
      const page: PluginPage = {
        title: path.basename(file, path.extname(file)),
        tags: [],
        outputPath: path.join(this.options.outputDir, relative),
        url: relative.split(path.sep).map(encodeURIComponent).join('/'),
        filePath: file,
        source: await fs.readFile(file, 'utf8'),
        data: {},
        content: '',
        output: ''
      };
      for (const plugin of this.plugins) await plugin.onFile?.(page);
      await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
      await fs.writeFile(page.outputPath, page.output);
      this.pages.push(page);
    }

    this.pages.sort((left, right) => {
      if (left.date && right.date && left.date !== right.date) return right.date.localeCompare(left.date);
      return left.title.localeCompare(right.title);
    });
    for (const plugin of this.plugins) await plugin.afterBuild?.(this.context());
    return this.pages.map(({ title, date, tags, outputPath, url }) => ({ title, date, tags, outputPath, url }));
  }

  async stop(): Promise<void> {
    if (!this.started) return;
    for (const plugin of this.plugins) await plugin.onEnd?.(this.context());
    this.started = false;
  }
}
