import fs from 'fs';
import { BuildOptions, Page } from './types';
import { Plugin, PluginContext, PluginPipeline, createContext } from './plugin';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/templates';

export function createDefaultPlugins(userPlugins: Plugin[] = []): Plugin[] {
  return [new MarkdownPlugin(), ...userPlugins, new TemplatePlugin()];
}

export class SSGEngine {
  private readonly pipeline: PluginPipeline;

  constructor(plugins: Plugin[]) {
    this.pipeline = new PluginPipeline(plugins);
  }

  getPlugins(): Plugin[] {
    return this.pipeline.getPlugins();
  }

  build(options: BuildOptions): Page[] {
    const context = createContext(options);

    this.pipeline.runOnStart(context);
    this.pipeline.runBeforeBuild(context);

    fs.mkdirSync(context.outputDir, { recursive: true });

    const pages = context.pages;
    for (let i = 0; i < pages.length; i++) {
      const transformed = this.pipeline.runOnFile(pages[i], context);
      if (transformed !== undefined) {
        pages[i] = transformed;
      }
    }

    this.pipeline.runAfterBuild(context);
    this.pipeline.runOnEnd(context);

    return context.pages;
  }

  async buildAsync(options: BuildOptions): Promise<Page[]> {
    const context = createContext(options);

    await this.pipeline.runOnStartAsync(context);
    await this.pipeline.runBeforeBuildAsync(context);

    await fs.promises.mkdir(context.outputDir, { recursive: true });

    const pages = context.pages;
    for (let i = 0; i < pages.length; i++) {
      const transformed = await this.pipeline.runOnFileAsync(pages[i], context);
      if (transformed !== undefined) {
        pages[i] = transformed;
      }
    }

    await this.pipeline.runAfterBuildAsync(context);
    await this.pipeline.runOnEndAsync(context);

    return context.pages;
  }
}

export function createEngine(userPlugins: Plugin[] = []): SSGEngine {
  return new SSGEngine(createDefaultPlugins(userPlugins));
}
