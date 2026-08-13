import { promises as fs } from 'node:fs';
import path from 'node:path';
import {
  defineConfig,
  loadPlugins,
  PluginPipeline,
  type Plugin,
  type PluginContext,
  type PluginPage,
  type SsgConfig,
} from './plugin';
import { MarkdownPlugin } from './plugins/markdown';
import { escapeHtml, renderDocument, TemplatePlugin } from './plugins/template';

export type { Plugin, PluginContext, PluginPage, SsgConfig } from './plugin';
export { defineConfig, MarkdownPlugin, TemplatePlugin };
export { DevServerPlugin } from './plugins/dev-server';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configFile?: string;
  plugins?: Plugin[];
}

export interface GeneratedPage {
  title: string;
  date?: string;
  tags: string[];
  outputPath: string;
  url: string;
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry): Promise<string[]> => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(entryPath);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

function indexBody(pages: PluginPage[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    const tags = page.tags.length > 0 ? ` <span>${page.tags.map(escapeHtml).join(', ')}</span>` : '';
    return `      <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}${tags}</li>`;
  });
  return `    <ul>\n${items.join('\n')}\n    </ul>`;
}

function isWithin(parent: string, candidate: string): boolean {
  const relative = path.relative(parent, candidate);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

function configuredPlugins(options: BuildOptions): Plugin[] {
  if (options.plugins) return options.plugins;
  return loadPlugins(options.configFile);
}

/** Build all Markdown documents and return metadata for the generated pages. */
export async function buildSite(options: BuildOptions = {}): Promise<GeneratedPage[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  if (isWithin(contentDir, outputDir) || isWithin(outputDir, contentDir)) {
    throw new Error('Content and output directories must not overlap');
  }

  const pages: PluginPage[] = [];
  const context: PluginContext = { contentDir, outputDir, templatesDir, pages };
  const pipeline = new PluginPipeline([
    new MarkdownPlugin(),
    new TemplatePlugin(templatesDir),
    ...configuredPlugins(options),
  ]);

  try {
    await pipeline.run('onStart', context);
    await pipeline.run('beforeBuild', context);
    for (const file of await markdownFiles(contentDir)) {
      const relativePath = path.relative(contentDir, file).replace(/\.md$/i, '.html');
      const page: PluginPage = {
        sourcePath: file,
        relativePath,
        outputPath: path.join(outputDir, relativePath),
        url: relativePath.split(path.sep).map(encodeURIComponent).join('/'),
        source: await fs.readFile(file, 'utf8'),
        data: {},
        title: path.basename(file, path.extname(file)),
        tags: [],
        content: '',
        html: '',
      };
      await pipeline.onFile(page);
      pages.push(page);
    }

    const outputPaths = new Set<string>();
    for (const page of pages) {
      const normalizedPath = page.outputPath.toLowerCase();
      if (path.basename(normalizedPath) === 'index.html' && path.dirname(page.outputPath) === outputDir) {
        throw new Error('A root index.md conflicts with the generated index.html');
      }
      if (outputPaths.has(normalizedPath)) {
        throw new Error(`Multiple Markdown files produce the same output: ${page.outputPath}`);
      }
      outputPaths.add(normalizedPath);
    }

    await fs.rm(outputDir, { recursive: true, force: true });
    for (const page of pages) {
      await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
      await fs.writeFile(page.outputPath, page.html, 'utf8');
    }
    await fs.mkdir(outputDir, { recursive: true });
    await fs.writeFile(path.join(outputDir, 'index.html'), renderDocument('Pages', indexBody(pages)), 'utf8');
    await pipeline.run('afterBuild', context);

    return pages.map(({ title, date, tags, outputPath, url }) => ({ title, date, tags, outputPath, url }));
  } finally {
    await pipeline.run('onEnd', context);
  }
}
