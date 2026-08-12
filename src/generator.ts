import { promises as fs } from 'node:fs';
import path from 'node:path';
import { BuildOptions, Page } from './types';
import { Plugin, PluginContext } from './plugin';
import { MarkdownPlugin, markdownFiles, parseMarkdown } from './markdown-plugin';
import { TemplatePlugin } from './template-plugin';
import { loadConfiguredPlugins } from './config';

const DEFAULT_CONTENT_DIR = './content';
const DEFAULT_OUTPUT_DIR = './dist';
const DEFAULT_TEMPLATES_DIR = './templates';

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character] as string));
}

function pageDocument(page: Page): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(page.frontmatter.title)}</title>\n</head>\n<body>\n<main>\n<h1>${escapeHtml(page.frontmatter.title)}</h1>\n${page.frontmatter.date ? `<time datetime="${escapeHtml(page.frontmatter.date)}">${escapeHtml(page.frontmatter.date)}</time>\n` : ''}${page.html}</main>\n</body>\n</html>\n`;
}

function indexDocument(pages: Page[]): string {
  const items = pages.map((page) => {
    const metadata = [page.frontmatter.date, ...page.frontmatter.tags].filter(Boolean).map(escapeHtml).join(' | ');
    return `<li><a href="${encodeURI(page.outputPath)}">${escapeHtml(page.frontmatter.title)}</a>${metadata ? ` <small>${metadata}</small>` : ''}</li>`;
  }).join('\n');
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Home</title>\n</head>\n<body>\n<main>\n<h1>Pages</h1>\n<ul>\n${items}\n</ul>\n</main>\n</body>\n</html>\n`;
}

async function runHook(plugins: Plugin[], hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', context: PluginContext): Promise<void> {
  for (const plugin of plugins) if (plugin[hook]) await plugin[hook]!(context);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir || DEFAULT_CONTENT_DIR);
  const outputDir = path.resolve(options.outputDir || DEFAULT_OUTPUT_DIR);
  const templatesDir = path.resolve(options.templatesDir || DEFAULT_TEMPLATES_DIR);
  const context: PluginContext = { options, contentDir, outputDir, templatesDir, pages: [] };
  const configured = await loadConfiguredPlugins(options.configFile, context, options.plugins);
  const plugins = [new MarkdownPlugin(), ...configured, new TemplatePlugin()];
  await runHook(plugins, 'onStart', context);
  await runHook(plugins, 'beforeBuild', context);
  const files = await markdownFiles(contentDir);
  for (const file of files) {
    let page: Page = { sourcePath: file, outputPath: '', slug: '', frontmatter: { title: '', tags: [] }, html: await fs.readFile(file, 'utf8') };
    for (const plugin of plugins) if (plugin.onFile) page = (await plugin.onFile(page, context)) || page;
    context.pages.push(page);
  }
  context.pages.sort((a, b) => a.slug.localeCompare(b.slug));
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(context.pages.map(async (page) => {
    const destination = path.join(outputDir, page.outputPath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, page.html === '' ? pageDocument(page) : page.html, 'utf8');
  }));
  await fs.writeFile(path.join(outputDir, 'index.html'), indexDocument(context.pages), 'utf8');
  await runHook(plugins, 'afterBuild', context);
  await runHook(plugins, 'onEnd', context);
  return context.pages;
}

export { escapeHtml, indexDocument, pageDocument, parseMarkdown };
