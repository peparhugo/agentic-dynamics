import fs from 'node:fs/promises';
import path from 'node:path';
import type { Plugin } from './plugin';
import { loadConfiguredPlugins } from './plugin';
import { MarkdownPlugin } from '../plugins/markdown';
import { TemplatePlugin } from '../plugins/template';

export interface PageMetadata { title: string; date?: string; tags: string[]; template?: string; layout?: string; }
export interface Page { sourcePath: string; outputPath: string; metadata: PageMetadata; html: string; }
export interface BuildOptions { contentDir?: string; outputDir?: string; templatesDir?: string; plugins?: Plugin[]; configPath?: string; }

const markdownExtensions = new Set(['.md', '.markdown']);

async function markdownFiles(directory: string): Promise<string[]> {
  const files: string[] = [];
  for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(entryPath));
    else if (markdownExtensions.has(path.extname(entry.name).toLowerCase())) files.push(entryPath);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

function indexDocument(pages: Page[], outputDir: string): string {
  const items = pages.map((page) => {
    const href = path.relative(outputDir, page.outputPath).replaceAll(path.sep, '/');
    const date = page.metadata.date ? ` <time>${page.metadata.date.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;')}</time>` : '';
    const title = page.metadata.title.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
    return `      <li><a href="${href.replaceAll('&', '&amp;').replaceAll('"', '&quot;')}">${title}</a>${date}</li>`;
  }).join('\n');
  return `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>Index</title>\n</head>\n<body>\n  <main><h1>Pages</h1><ul>${items}</ul></main>\n</body>\n</html>\n`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const resolved = { contentDir: path.resolve(options.contentDir ?? './content'), outputDir: path.resolve(options.outputDir ?? './dist'), templatesDir: path.resolve(options.templatesDir ?? './templates') };
  const context = { options: resolved, pages: [] as Page[] };
  const plugins = [new MarkdownPlugin(), new TemplatePlugin(), ...loadConfiguredPlugins(options.configPath), ...(options.plugins ?? [])];
  for (const plugin of plugins) await plugin.onStart?.(context);
  try {
    for (const plugin of plugins) await plugin.beforeBuild?.(context);
    for (const sourcePath of await markdownFiles(resolved.contentDir)) {
      const relativePath = path.relative(resolved.contentDir, sourcePath);
      let page: Page = { sourcePath, outputPath: path.join(resolved.outputDir, relativePath.replace(/\.(md|markdown)$/i, '.html')), metadata: { title: path.basename(sourcePath, path.extname(sourcePath)), tags: [] }, html: '' };
      for (const plugin of plugins) { const result = await plugin.onFile?.(page, context); if (result) page = result; }
      context.pages.push(page);
    }
    await fs.mkdir(resolved.outputDir, { recursive: true });
    for (const page of context.pages) { await fs.mkdir(path.dirname(page.outputPath), { recursive: true }); await fs.writeFile(page.outputPath, page.html, 'utf8'); }
    await fs.writeFile(path.join(resolved.outputDir, 'index.html'), indexDocument(context.pages, resolved.outputDir), 'utf8');
    for (const plugin of plugins) await plugin.afterBuild?.(context);
    return context.pages;
  } finally {
    for (const plugin of plugins) await plugin.onEnd?.(context);
  }
}

export type { BuildContext, Plugin, PluginExport, SsgConfig } from './plugin';
export { loadConfiguredPlugins } from './plugin';
