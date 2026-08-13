import { existsSync, readFileSync } from 'node:fs';
import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { dirname, extname, join, resolve } from 'node:path';
import type { BuildOptions, Page } from './generator';
import { MarkdownPlugin, TemplatePlugin, type Plugin, type PluginContext, type PluginFile } from './plugins';

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return ['.md', '.markdown'].includes(extname(entry.name).toLowerCase()) ? [path] : [];
  }));
  return files.flat();
}

async function loadConfiguredPlugins(): Promise<Plugin[]> {
  const configPath = resolve('ssg.config.ts');
  if (!existsSync(configPath)) return [];

  // TypeScript configs and their local plugin imports are transpiled on demand.
  const typescript = await import('typescript');
  const previous = require.extensions['.ts'];
  require.extensions['.ts'] = (module, filename) => {
    const source = readFileSync(filename, 'utf8');
    const output = typescript.transpileModule(source, { compilerOptions: { module: typescript.ModuleKind.CommonJS, target: typescript.ScriptTarget.ES2022 } });
    module._compile(output.outputText, filename);
  };
  try {
    delete require.cache[configPath];
    const config = require(configPath) as { default?: Plugin[]; plugins?: Plugin[] };
    const plugins = config.default ?? config.plugins ?? [];
    if (!Array.isArray(plugins)) throw new Error('ssg.config.ts must export a plugin array or { plugins: Plugin[] }');
    return plugins;
  } finally {
    if (previous === undefined) delete require.extensions['.ts'];
    else require.extensions['.ts'] = previous;
  }
}

export class SsgEngine {
  constructor(private readonly plugins: Plugin[]) {}

  async build(options: BuildOptions = {}): Promise<Page[]> {
    const resolvedOptions: Required<BuildOptions> = {
      contentDir: options.contentDir ?? './content',
      outputDir: options.outputDir ?? './dist',
      templateDir: options.templateDir ?? './templates',
    };
    if (!existsSync(resolvedOptions.contentDir)) throw new Error(`Content directory does not exist: ${resolvedOptions.contentDir}`);
    const context: PluginContext = { options: resolvedOptions, pages: [] };
    await this.run('onStart', context);
    try {
      await this.run('beforeBuild', context);
      const files = await markdownFiles(resolvedOptions.contentDir);
      await rm(resolvedOptions.outputDir, { recursive: true, force: true });
      await mkdir(resolvedOptions.outputDir, { recursive: true });
      for (const source of files) {
        const file: PluginFile = { source, data: {}, title: '', tags: [], slug: '', html: '' };
        context.file = file;
        await this.run('onFile', context, file);
        if (file.output !== undefined) {
          const destination = join(resolvedOptions.outputDir, file.slug);
          await mkdir(dirname(destination), { recursive: true });
          await writeFile(destination, file.output, 'utf8');
        }
        context.pages.push({ title: file.title, date: file.date, tags: file.tags, slug: file.slug, html: file.html });
      }
      context.file = undefined;
      context.pages.sort((left, right) => left.title.localeCompare(right.title));
      await this.run('afterBuild', context);
      return context.pages;
    } finally {
      context.file = undefined;
      await this.run('onEnd', context);
    }
  }

  private async run(hook: keyof Plugin, context: PluginContext, file?: PluginFile): Promise<void> {
    for (const plugin of this.plugins) {
      const callback = plugin[hook];
      if (callback === undefined) continue;
      if (hook === 'onFile' && file !== undefined) await callback.call(plugin, file, context);
      else await (callback as (value: PluginContext) => void | Promise<void>).call(plugin, context);
    }
  }
}

export async function createEngine(plugins: Plugin[] = []): Promise<SsgEngine> {
  return new SsgEngine([new MarkdownPlugin(), ...plugins, ...await loadConfiguredPlugins(), new TemplatePlugin()]);
}
