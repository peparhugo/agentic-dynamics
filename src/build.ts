import * as fs from 'fs';
import * as path from 'path';
import { BuildOptions, Page, normalizeTags, parseFrontmatter } from './ssg';
import { Plugin, PluginContext, applyOnFile, createPluginContext, runSyncHooks } from './plugin';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { loadConfiguredPlugins } from './load-plugins';

function slugFromFilename(filename: string): string {
  const ext = path.extname(filename);
  return filename.slice(0, filename.length - ext.length);
}

/** Recursively collect all .md file paths under a directory, sorted by path. */
export function findMarkdownFiles(contentDir: string): string[] {
  const results: string[] = [];

  function walk(dir: string): void {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
        results.push(full);
      }
    }
  }

  if (fs.existsSync(contentDir)) {
    walk(contentDir);
  }
  return results;
}

function loadRawPages(contentDir: string): Page[] {
  const files = findMarkdownFiles(contentDir);
  const pages: Page[] = [];

  for (const file of files) {
    const raw = fs.readFileSync(file, 'utf8');
    const { frontmatter, content } = parseFrontmatter(raw);
    const slug = slugFromFilename(path.basename(file));
    pages.push({
      slug,
      title: frontmatter.title || slug,
      date: frontmatter.date,
      tags: normalizeTags(frontmatter.tags),
      html: '',
      content,
      template: frontmatter.template,
      layout: frontmatter.layout,
      frontmatter,
    });
  }

  return pages.sort((a, b) => {
    const ad = a.date || '';
    const bd = b.date || '';
    if (ad === bd) {
      return a.title.localeCompare(b.title);
    }
    return ad < bd ? 1 : -1;
  });
}

export function loadPages(contentDir: string): Page[] {
  const markdown = new MarkdownPlugin();
  return loadRawPages(contentDir).map((page) => markdown.render(page));
}

export interface BuildResult {
  outputDir: string;
  writtenFiles: string[];
}

export function build(options: BuildOptions): BuildResult {
  const markdown = new MarkdownPlugin();
  const template = new TemplatePlugin({ templatesDir: options.templatesDir });
  const plugins: Plugin[] = [markdown, template, ...loadConfiguredPlugins()];

  const context: PluginContext = createPluginContext(options);

  runSyncHooks(plugins, 'onStart', context);
  runSyncHooks(plugins, 'beforeBuild', context);

  const pages: Page[] = loadRawPages(options.contentDir).map((page) =>
    applyOnFile(plugins, page, context)
  );
  context.pages = pages;

  fs.mkdirSync(options.outputDir, { recursive: true });

  const writtenFiles: string[] = [];

  const indexHtml = template.renderIndex(pages);
  const indexPath = path.join(options.outputDir, 'index.html');
  fs.writeFileSync(indexPath, indexHtml, 'utf8');
  writtenFiles.push(indexPath);

  for (const page of pages) {
    const pageHtml = template.renderPage(page);
    const pagePath = path.join(options.outputDir, `${page.slug}.html`);
    fs.writeFileSync(pagePath, pageHtml, 'utf8');
    writtenFiles.push(pagePath);
  }

  context.writtenFiles = writtenFiles;
  runSyncHooks(plugins, 'afterBuild', context);
  runSyncHooks(plugins, 'onEnd', context);

  return { outputDir: options.outputDir, writtenFiles };
}
