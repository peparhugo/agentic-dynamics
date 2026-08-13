import { promises as fs } from 'node:fs';
import path from 'node:path';
import { resolveConfig } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { indexDocument, TemplatePlugin } from './plugins/template';
import type { BuildOptions, Page, Plugin, PluginContext, PluginPage, ResolvedBuildOptions } from './plugin';

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(entryPath);
    return /\.md$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

function publicPage(page: PluginPage): Page {
  return { title: page.title, date: page.date, tags: page.tags, outputPath: page.outputPath };
}

export interface BuildEngine {
  readonly context: PluginContext;
  readonly plugins: Plugin[];
  start(): Promise<void>;
  build(): Promise<Page[]>;
  end(): Promise<void>;
}

export async function createBuildEngine(options: BuildOptions = {}, additionalPlugins: Plugin[] = []): Promise<BuildEngine> {
  const { config, baseDir } = await resolveConfig(options);
  const resolveDirectory = (value: string | undefined, fallback: string): string =>
    path.resolve(baseDir, value ?? fallback);
  const resolved: ResolvedBuildOptions = {
    contentDir: resolveDirectory(options.contentDir ?? config.contentDir, './content'),
    outputDir: resolveDirectory(options.outputDir ?? config.outputDir, './dist'),
    templatesDir: resolveDirectory(options.templatesDir ?? config.templatesDir, './templates')
  };
  const plugins: Plugin[] = [
    new MarkdownPlugin(),
    new TemplatePlugin(),
    ...(config.plugins ?? []),
    ...(options.plugins ?? []),
    ...additionalPlugins
  ];
  let started = false;
  let ended = false;
  let building = false;

  const context: PluginContext = {
    options: resolved,
    pages: [],
    build: async () => engine.build()
  };
  const run = async (hook: keyof Plugin): Promise<void> => {
    for (const plugin of plugins) {
      const callback = plugin[hook];
      if (typeof callback === 'function') {
        await (callback as (context: PluginContext) => void | Promise<void>).call(plugin, context);
      }
    }
  };
  const engine: BuildEngine = {
    context,
    plugins,
    async start(): Promise<void> {
      if (started) return;
      started = true;
      await run('onStart');
    },
    async build(): Promise<Page[]> {
      if (building) throw new Error('A build is already in progress');
      building = true;
      try {
        await engine.start();
        context.pages = [];
        await run('beforeBuild');
        await fs.mkdir(resolved.outputDir, { recursive: true });
        for (const file of await markdownFiles(resolved.contentDir)) {
          const relativePath = path.relative(resolved.contentDir, file).replace(/\.md$/i, '.html');
          const page: PluginPage = {
            title: path.basename(file, path.extname(file)),
            tags: [],
            outputPath: relativePath,
            sourcePath: file,
            source: await fs.readFile(file, 'utf8'),
            data: {},
            content: '',
            html: ''
          };
          for (const plugin of plugins) await plugin.onFile?.(page, context);
          const destination = path.join(resolved.outputDir, page.outputPath);
          await fs.mkdir(path.dirname(destination), { recursive: true });
          await fs.writeFile(destination, page.html, 'utf8');
          context.pages.push(page);
        }
        context.pages.sort((left, right) => {
          if (left.date && right.date && left.date !== right.date) return right.date.localeCompare(left.date);
          if (left.date !== right.date) return left.date ? -1 : 1;
          return left.title.localeCompare(right.title);
        });
        await fs.writeFile(path.join(resolved.outputDir, 'index.html'), indexDocument(context.pages), 'utf8');
        await run('afterBuild');
        return context.pages.map(publicPage);
      } finally {
        building = false;
      }
    },
    async end(): Promise<void> {
      if (!started || ended) return;
      ended = true;
      await run('onEnd');
    }
  };
  return engine;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const engine = await createBuildEngine(options);
  try {
    return await engine.build();
  } finally {
    await engine.end();
  }
}
