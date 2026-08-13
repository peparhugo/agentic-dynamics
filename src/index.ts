import { promises as fs } from 'node:fs';
import path from 'node:path';
import { loadPlugins } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import {
  BuildContext,
  BuildOptions,
  GeneratedPage,
  Page,
  Plugin,
  ResolvedBuildOptions,
} from './plugin';

async function markdownFiles(directory: string): Promise<string[]> {
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') throw new Error(`Content directory does not exist: ${directory}`);
    throw error;
  }
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(entryPath);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

async function runHook<K extends 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd'>(
  plugins: Plugin[],
  hook: K,
  context: BuildContext,
): Promise<void> {
  for (const plugin of plugins) await plugin[hook]?.(context);
}

export class SsgEngine {
  readonly options: ResolvedBuildOptions;
  readonly plugins: Plugin[];

  constructor(options: ResolvedBuildOptions, plugins: Plugin[]) {
    this.options = options;
    this.plugins = plugins;
  }

  async build(): Promise<GeneratedPage[]> {
    const context: BuildContext = { options: this.options, pages: [] };
    try {
      await runHook(this.plugins, 'onStart', context);
      await runHook(this.plugins, 'beforeBuild', context);
      const files = await markdownFiles(this.options.contentDir);
      await fs.rm(this.options.outputDir, { recursive: true, force: true });
      await fs.mkdir(this.options.outputDir, { recursive: true });

      for (const sourcePath of files) {
        const relativePath = path.relative(this.options.contentDir, sourcePath);
        const outputRelativePath = relativePath.replace(/\.md$/i, '.html');
        const page: Page = {
          sourcePath,
          outputPath: path.join(this.options.outputDir, outputRelativePath),
          url: outputRelativePath.split(path.sep).join('/'),
          source: await fs.readFile(sourcePath, 'utf8'),
          content: '',
          data: {},
          title: path.basename(sourcePath, path.extname(sourcePath)),
          tags: [],
          body: '',
          html: '',
        };
        for (const plugin of this.plugins) await plugin.onFile?.(page, context);
        await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
        await fs.writeFile(page.outputPath, page.html, 'utf8');
        context.pages.push(page);
      }
      context.pages.sort((left, right) => left.title.localeCompare(right.title));
      await runHook(this.plugins, 'afterBuild', context);
      return context.pages.map(({ title, date, tags, sourcePath, outputPath, url }) => ({
        title, date, tags, sourcePath, outputPath, url,
      }));
    } finally {
      await runHook(this.plugins, 'onEnd', context);
    }
  }
}

export async function createEngine(options: BuildOptions = {}): Promise<SsgEngine> {
  const configFile = path.resolve(options.configFile ?? './ssg.config.ts');
  const resolved: ResolvedBuildOptions = {
    contentDir: path.resolve(options.contentDir ?? './content'),
    outputDir: path.resolve(options.outputDir ?? './dist'),
    templatesDir: path.resolve(options.templatesDir ?? './templates'),
    configFile,
  };
  const configured = options.plugins ?? await loadPlugins(configFile);
  return new SsgEngine(resolved, [new MarkdownPlugin(), new TemplatePlugin(), ...configured]);
}

export async function buildSite(options: BuildOptions = {}): Promise<GeneratedPage[]> {
  return (await createEngine(options)).build();
}

export * from './plugin';
export { MarkdownPlugin } from './plugins/markdown';
export { TemplatePlugin } from './plugins/template';
export { DevServerPlugin } from './plugins/dev-server';
export { DevServer, ServeOptions, startDevServer } from './server';
