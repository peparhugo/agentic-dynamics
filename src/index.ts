import fs from 'node:fs';
import path from 'node:path';
import type { Plugin, PluginConfig, PluginContext } from './plugin';
import { MarkdownPlugin, pageFromMarkdown } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
export { renderTemplate } from './template';
export * from './plugin';
export { MarkdownPlugin } from './plugins/markdown';
export { TemplatePlugin } from './plugins/template';
export { DevServerPlugin } from './plugins/dev-server';

export interface Frontmatter { title?: string; date?: string | Date; tags?: string[] | string; [key: string]: unknown; }
export interface SitePage { title: string; date?: string; tags: string[]; source: string; output: string; template?: string; layout?: string; }
export interface BuildOptions { contentDir?: string; outputDir?: string; templatesDir?: string; plugins?: PluginConfig[]; configFile?: string; }

function markdownFiles(directory: string): string[] {
  if (!fs.existsSync(directory)) return [];
  const files: string[] = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...markdownFiles(file));
    else if (/\.md$/i.test(entry.name)) files.push(file);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

function loadPlugins(options: BuildOptions): Plugin[] {
  const configPath = path.resolve(options.configFile ?? './ssg.config.ts');
  let configured: PluginConfig[] = options.plugins ?? [];
  if (options.plugins === undefined && fs.existsSync(configPath)) {
    // Config is intentionally required at build time so it works with ts-jest and ts-node.
    const loaded = require(configPath) as { default?: PluginConfig[] | { plugins?: PluginConfig[] }; plugins?: PluginConfig[] };
    const value = loaded.default ?? loaded;
    configured = Array.isArray(value) ? value : value.plugins ?? [];
  }
  return configured.map((entry) => {
    if (typeof entry === 'string') {
      const loaded = require(path.resolve(entry));
      return (loaded.default ?? loaded) as Plugin;
    }
    return typeof entry === 'function' ? entry() : entry;
  });
}

function indexHtml(pages: SitePage[]): string {
  const escape = (value: string) => value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const items = pages.map((page) => `    <li><a href="${escape(page.output)}">${escape(page.title)}</a>${page.date ? ` <time>${escape(page.date)}</time>` : ''}</li>`).join('\n');
  return `<!doctype html>\n<html>\n<head><meta charset="utf-8"><title>Index</title></head>\n<body>\n  <h1>Pages</h1>\n  <ul>\n${items}\n  </ul>\n</body>\n</html>\n`;
}

export function buildSite(options: BuildOptions = {}): SitePage[] {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const pages = markdownFiles(contentDir).map((file) => pageFromMarkdown(file, contentDir));
  const context: PluginContext = { options, contentDir, outputDir, templatesDir, pages };
  const plugins = [new MarkdownPlugin(), ...loadPlugins(options), new TemplatePlugin()];
  plugins.forEach((plugin) => plugin.onStart?.(context));
  try {
    plugins.forEach((plugin) => plugin.beforeBuild?.(context));
    fs.rmSync(outputDir, { recursive: true, force: true });
    fs.mkdirSync(outputDir, { recursive: true });
    pages.forEach((page) => {
      plugins.forEach((plugin) => plugin.onFile?.(page, context));
      const rendered = (page as SitePage & { rendered?: string }).rendered ?? '';
      const destination = path.join(outputDir, page.output);
      fs.mkdirSync(path.dirname(destination), { recursive: true });
      fs.writeFileSync(destination, rendered);
    });
    pages.sort((a, b) => a.title.localeCompare(b.title));
    fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml(pages));
    plugins.forEach((plugin) => plugin.afterBuild?.(context));
  } finally {
    plugins.forEach((plugin) => plugin.onEnd?.(context));
  }
  return pages;
}

export { indexHtml, markdownFiles };
