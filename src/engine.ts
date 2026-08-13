import { promises as fs } from 'node:fs';
import path from 'node:path';
import { loadPlugins } from './config';
import { renderIndex } from './output';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import type { BuildOptions, GeneratedPage, Plugin, PluginContext, PluginPage } from './types';

const DEFAULT_CONTENT_DIR = './content';
const DEFAULT_OUTPUT_DIR = './dist';
const DEFAULT_TEMPLATES_DIR = './templates';

async function findMarkdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return findMarkdownFiles(entryPath);
    return /\.md$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

async function runHook(
  plugins: Plugin[],
  hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd',
  context: PluginContext,
): Promise<void> {
  for (const plugin of plugins) await plugin[hook]?.(context);
}

export async function buildSite(options: BuildOptions = {}): Promise<GeneratedPage[]> {
  const contentDir = path.resolve(options.contentDir ?? DEFAULT_CONTENT_DIR);
  const outputDir = path.resolve(options.outputDir ?? DEFAULT_OUTPUT_DIR);
  const templatesDir = path.resolve(options.templatesDir ?? DEFAULT_TEMPLATES_DIR);
  const configuredPlugins = await loadPlugins(options.configFile);
  const plugins: Plugin[] = [
    new MarkdownPlugin(),
    ...configuredPlugins,
    ...(options.plugins ?? []),
    new TemplatePlugin(),
  ];
  const context: PluginContext = { contentDir, outputDir, templatesDir, pages: [] };

  await runHook(plugins, 'onStart', context);
  try {
    const files = await findMarkdownFiles(contentDir);
    context.pages = await Promise.all(files.map(async (sourcePath): Promise<PluginPage> => {
      const relativePath = path.relative(contentDir, sourcePath);
      const relativeOutput = relativePath.replace(/\.md$/i, '.html');
      return {
        title: path.basename(relativePath, path.extname(relativePath)),
        tags: [],
        sourcePath,
        outputPath: path.join(outputDir, relativeOutput),
        url: relativeOutput.split(path.sep).join('/'),
        source: await fs.readFile(sourcePath, 'utf8'),
        content: '',
        html: '',
        output: '',
        frontmatter: {},
      };
    }));

    await fs.rm(outputDir, { recursive: true, force: true });
    await runHook(plugins, 'beforeBuild', context);
    for (const page of context.pages) {
      for (const plugin of plugins) await plugin.onFile?.(page, context);
    }
    context.pages.sort((left, right) => {
      if (left.date && right.date && left.date !== right.date) return right.date.localeCompare(left.date);
      if (left.date !== right.date) return left.date ? -1 : 1;
      return left.title.localeCompare(right.title);
    });
    await Promise.all(context.pages.map(async (page) => {
      await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
      await fs.writeFile(page.outputPath, page.output, 'utf8');
    }));
    await fs.mkdir(outputDir, { recursive: true });
    await fs.writeFile(path.join(outputDir, 'index.html'), renderIndex(context.pages), 'utf8');
    await runHook(plugins, 'afterBuild', context);
  } finally {
    await runHook(plugins, 'onEnd', context);
  }

  return context.pages.map((page) => ({
    title: page.title,
    date: page.date,
    tags: page.tags,
    sourcePath: page.sourcePath,
    outputPath: page.outputPath,
    url: page.url,
  }));
}
