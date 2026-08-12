import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { DEFAULT_TEMPLATE_DIR } from './templates';
import { collectMarkdownFiles, comparePages, renderIndex, toSlug } from './render';
import { PluginManager, type Plugin, type PluginContext, type PluginFile } from './plugin';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/templates';
import { loadConfig } from './config';
import type { BuildResult, Page } from './types';

export interface SSGEngineOptions {
  plugins?: Plugin[];
  templatesDir?: string;
  port?: number;
  configPath?: string;
}

export class SSGEngine {
  private readonly manager: PluginManager;
  private readonly options: SSGEngineOptions;

  constructor(options: SSGEngineOptions = {}) {
    this.options = options;
    const config = loadConfig(options.configPath ?? 'ssg.config.ts');
    const configured = [...(config?.plugins ?? []), ...(options.plugins ?? [])];

    const plugins: Plugin[] = [];
    if (!configured.some((plugin) => plugin.name === 'markdown')) {
      plugins.push(new MarkdownPlugin());
    }
    if (!configured.some((plugin) => plugin.name === 'templates')) {
      plugins.push(new TemplatePlugin(options.templatesDir));
    }
    plugins.push(...configured);

    this.manager = new PluginManager(plugins);
  }

  getPlugins(): Plugin[] {
    return this.manager.getPlugins();
  }

  addPlugin(plugin: Plugin): void {
    this.manager.register(plugin);
  }

  async build(contentDir: string, outputDir: string): Promise<BuildResult> {
    const templatesDir = this.options.templatesDir ?? DEFAULT_TEMPLATE_DIR;
    const context: PluginContext = {
      contentDir,
      outputDir,
      templatesDir,
      port: this.options.port ?? 3000,
      pages: [],
      files: [],
      options: { ...this.options },
    };

    await this.manager.runHook('onStart', context);
    await this.manager.runHook('beforeBuild', context);

    const works = await this.collectPages(contentDir);
    const pages: PluginFile[] = [];
    for (const work of works) {
      pages.push(await this.manager.runOnFile(work, context));
    }
    pages.sort(comparePages);
    context.pages = pages;

    await mkdir(outputDir, { recursive: true });
    const files: string[] = [];
    for (const page of pages) {
      const outPath = path.join(outputDir, `${page.slug}.html`);
      await mkdir(path.dirname(outPath), { recursive: true });
      await writeFile(outPath, page.html, 'utf8');
      files.push(outPath);
    }
    const indexPath = path.join(outputDir, 'index.html');
    await writeFile(indexPath, renderIndex(pages), 'utf8');
    files.push(indexPath);
    context.files = files;

    await this.manager.runHook('afterBuild', context);
    await this.manager.runHook('onEnd', context);

    return { pages, files };
  }

  private async collectPages(contentDir: string): Promise<PluginFile[]> {
    const files = await collectMarkdownFiles(contentDir);
    const works: PluginFile[] = [];
    for (const file of files) {
      const raw = await readFile(file, 'utf8');
      const relative = path.relative(contentDir, file);
      works.push({
        title: '',
        date: '',
        tags: [],
        slug: toSlug(relative),
        source: relative,
        html: '',
        raw,
        contentDir,
      });
    }
    return works;
  }
}

export type { Page };
