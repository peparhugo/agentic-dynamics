import { basename, extname } from 'path';
import { Page } from './page';
import { Plugin, PluginContext } from './plugin';
import { loadPlugins } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { listMarkdownFiles } from './files';

export interface SsgOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  plugins?: Plugin[];
}

function defaultPlugins(): Plugin[] {
  return [new MarkdownPlugin(), new TemplatePlugin()];
}

function buildPipeline(extra: Plugin[] | undefined): Plugin[] {
  const pipeline = defaultPlugins()
    .concat(loadPlugins())
    .concat(extra ?? []);
  const names = new Set<string>();
  const unique: Plugin[] = [];
  for (const plugin of pipeline) {
    if (names.has(plugin.name)) continue;
    names.add(plugin.name);
    unique.push(plugin);
  }
  return unique;
}

export function createEngine(options: SsgOptions): SsgEngine {
  return new SsgEngine(options);
}

export class SsgEngine {
  private readonly plugins: Plugin[];
  private readonly context: PluginContext;

  constructor(options: SsgOptions) {
    this.context = {
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir,
    };
    this.plugins = buildPipeline(options.plugins);
  }

  get pipeline(): Plugin[] {
    return this.plugins;
  }

  start(): void {
    for (const plugin of this.plugins) {
      plugin.onStart?.(this.context);
    }
  }

  build(): Page[] {
    for (const plugin of this.plugins) {
      plugin.beforeBuild?.(this.context);
    }

    const files = listMarkdownFiles(this.context.contentDir);
    const pages: Page[] = [];
    for (const file of files) {
      let page: Page = {
        slug: basename(file, extname(file)),
        title: '',
        date: '',
        tags: [],
        contentHtml: '',
        filePath: file,
      };
      for (const plugin of this.plugins) {
        const result = plugin.onFile?.(page, this.context);
        if (result) page = result;
      }
      pages.push(page);
    }
    pages.sort((a, b) => b.date.localeCompare(a.date));

    for (const plugin of this.plugins) {
      plugin.afterBuild?.(this.context, pages);
    }
    for (const plugin of this.plugins) {
      plugin.onEnd?.(this.context);
    }

    return pages;
  }
}
