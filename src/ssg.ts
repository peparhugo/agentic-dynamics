import * as fs from 'fs';
import * as path from 'path';
import { loadPlugins } from './config';
import { parseFrontmatter } from './frontmatter';
import { PluginPipeline, type Plugin, type SsgContext } from './plugin';
import type { SiteConfig } from './template';
import type { Page } from './types';

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  siteTitle?: string;
  templatesDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
  configPath?: string;
}

export const DEFAULT_CONTENT_DIR = './content';
export const DEFAULT_OUTPUT_DIR = './dist';
export const DEFAULT_TEMPLATES_DIR = './templates';
export const DEFAULT_SITE_TITLE = 'My Static Site';

const MARKDOWN_EXTENSION = /\.(md|markdown)$/i;

export function collectMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) return [];

  const files: string[] = [];
  const walk = (dir: string): void => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && MARKDOWN_EXTENSION.test(entry.name)) {
        files.push(full);
      }
    }
  };
  walk(contentDir);
  return files.sort();
}

export function slugFor(filePath: string, contentDir: string): string {
  const relative = path.relative(contentDir, filePath).replace(/\\/g, '/');
  return relative.replace(MARKDOWN_EXTENSION, '');
}

function toSiteConfig(options: BuildOptions): SiteConfig {
  return {
    title: options.siteTitle ?? DEFAULT_SITE_TITLE,
    templatesDir: options.templatesDir ? path.resolve(options.templatesDir) : path.resolve(DEFAULT_TEMPLATES_DIR),
    defaultTemplate: options.defaultTemplate,
    defaultLayout: options.defaultLayout,
  };
}

function createContext(options: BuildOptions): SsgContext {
  return {
    contentDir: path.resolve(options.contentDir),
    outputDir: path.resolve(options.outputDir),
    siteConfig: toSiteConfig(options),
    pages: [],
    options: { ...options },
  };
}

export class Ssg {
  private readonly pipeline: PluginPipeline;

  constructor(plugins: Plugin[]) {
    this.pipeline = new PluginPipeline(plugins);
  }

  static async create(options: { plugins?: Plugin[]; configPath?: string } = {}): Promise<Ssg> {
    const plugins = options.plugins ?? (await loadPlugins(options.configPath));
    return new Ssg(plugins);
  }

  getPlugins(): Plugin[] {
    return this.pipeline.getPlugins();
  }

  build(options: BuildOptions): Promise<Page[]> {
    return this.run(options, true);
  }

  rebuild(options: BuildOptions): Promise<Page[]> {
    return this.run(options, false);
  }

  private async run(options: BuildOptions, runStart: boolean): Promise<Page[]> {
    const context = createContext(options);

    if (runStart) {
      await this.pipeline.onStart(context);
    }
    await this.pipeline.beforeBuild(context);

    for (const file of collectMarkdownFiles(context.contentDir)) {
      const source = fs.readFileSync(file, 'utf8');
      const { data, content } = parseFrontmatter(source);
      const slug = slugFor(file, context.contentDir);
      const page: Page = {
        slug,
        link: `${slug}.html`,
        outputPath: path.join(context.outputDir, `${slug}.html`),
        filePath: file,
        data,
        content,
        html: '',
        template: data.template,
        layout: data.layout,
      };
      context.pages.push(page);
      await this.pipeline.onFile(page, context);
    }

    fs.mkdirSync(context.outputDir, { recursive: true });
    await this.pipeline.afterBuild(context);
    await this.pipeline.onEnd(context);

    return context.pages;
  }
}

export async function buildSite(options: BuildOptions): Promise<Page[]> {
  const engine = await Ssg.create({ configPath: options.configPath });
  return engine.build(options);
}
