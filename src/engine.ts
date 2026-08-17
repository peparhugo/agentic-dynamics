import fs from 'fs';
import path from 'path';
import { Plugin, PluginContext, PluginPipeline } from './plugin';
import { BuildOptions, Page, Site } from './types';
import { escapeHtml } from './markdown';
import { loadConfig } from './config';
import { MarkdownPlugin } from './plugins/markdown-plugin';
import { TemplatePlugin } from './plugins/template-plugin';

export const DEFAULT_CONTENT_DIR = 'content';
export const DEFAULT_OUTPUT_DIR = 'dist';
export const DEFAULT_TEMPLATES_DIR = 'templates';

function listMarkdownFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) {
    return [];
  }
  const results: string[] = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...listMarkdownFiles(full));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
      results.push(full);
    }
  }
  return results;
}

function deriveSlug(filePath: string, contentDir: string): string {
  const relative = path.relative(contentDir, filePath);
  const parsed = path.parse(relative);
  return path.join(parsed.dir, parsed.name).split(path.sep).join('/');
}

function renderIndex(pages: Page[]): string {
  const items = pages
    .map((page) => {
      const date = page.date ? ` <span class="date">${escapeHtml(page.date)}</span>` : '';
      return `<li><a href="${escapeHtml(page.slug)}.html">${escapeHtml(
        page.title
      )}</a>${date}</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Index</title>
</head>
<body>
<h1>All Pages</h1>
<ul>
${items}
</ul>
</body>
</html>
`;
}

function resolvePluginModule(spec: string, context: PluginContext): Plugin | undefined {
  try {
    const resolved = require.resolve(spec, { paths: [process.cwd()] });
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const loaded = require(resolved);
    const exported = loaded && 'default' in loaded ? loaded.default : loaded;
    if (typeof exported === 'function') {
      const instance = new (exported as new (ctx: PluginContext) => Plugin)(context);
      return instance;
    }
    if (exported && typeof exported === 'object' && typeof exported.name === 'string') {
      return exported as Plugin;
    }
  } catch {
    // Ignore plugins that cannot be resolved or instantiated.
  }
  return undefined;
}

/**
 * Assemble the plugin pipeline: the built-in markdown and template plugins run
 * first, followed by any plugins declared in the project configuration.
 */
export function buildPlugins(context: PluginContext): Plugin[] {
  const plugins: Plugin[] = [new MarkdownPlugin(), new TemplatePlugin(context)];

  const config = loadConfig(process.cwd());
  for (const spec of config.plugins ?? []) {
    const plugin = resolvePluginModule(spec, context);
    if (plugin) {
      plugins.push(plugin);
    }
  }

  return plugins;
}

export function createEngine(options: BuildOptions): {
  context: PluginContext;
  pipeline: PluginPipeline;
} {
  const contentDir = path.resolve(options.contentDir ?? DEFAULT_CONTENT_DIR);
  const outputDir = path.resolve(options.outputDir ?? DEFAULT_OUTPUT_DIR);
  const templatesDir = options.templatesDir ?? DEFAULT_TEMPLATES_DIR;

  const context: PluginContext = {
    options,
    contentDir,
    outputDir,
    templatesDir,
    pages: [],
  };

  const pipeline = new PluginPipeline(buildPlugins(context));

  return { context, pipeline };
}

/**
 * Build the static site: read markdown from contentDir and write HTML files
 * (one per page plus an index.html) into outputDir. The core engine only
 * orchestrates the plugin pipeline; parsing and rendering are delegated to the
 * built-in MarkdownPlugin and TemplatePlugin.
 */
export function buildSite(options: BuildOptions): Site {
  const { context, pipeline } = createEngine(options);

  pipeline.runSync('onStart');
  pipeline.runSync('beforeBuild');

  const files = listMarkdownFiles(context.contentDir).sort();

  const pages: Page[] = files.map((file) => {
    const page: Page = {
      slug: deriveSlug(file, context.contentDir),
      title: '',
      date: undefined,
      tags: [],
      html: '',
      sourcePath: file,
      frontmatter: {},
      template: undefined,
      layout: undefined,
    };
    pipeline.runFileSync(page);
    return page;
  });

  pages.sort((a, b) => {
    if (a.date && b.date) {
      return b.date.localeCompare(a.date);
    }
    if (a.date) return -1;
    if (b.date) return 1;
    return a.title.localeCompare(b.title);
  });

  context.pages = pages;

  fs.mkdirSync(context.outputDir, { recursive: true });

  pipeline.runSync('afterBuild');

  fs.writeFileSync(path.join(context.outputDir, 'index.html'), renderIndex(pages));

  pipeline.runSync('onEnd');

  return { pages, outputDir: context.outputDir };
}
