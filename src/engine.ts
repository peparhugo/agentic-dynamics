import fs from 'fs';
import path from 'path';
import { Plugin, PluginContext, PluginPipeline } from './plugin';
import { BuildOptions, Page, Site } from './types';
import { escapeHtml, splitFrontmatter } from './markdown';
import { loadConfig } from './config';
import { MarkdownPlugin } from './plugins/markdown-plugin';
import { TemplatePlugin } from './plugins/template-plugin';
import {
  CacheEntry,
  CacheManifest,
  CACHE_FILENAME,
  computeTemplateHash,
  defaultManifest,
  hashFile,
  loadManifest,
  saveManifest,
} from './cache';

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
 *
 * When `incremental` is set (and `clean` is not), the engine compares each
 * page's source and template fingerprints against the `.ssg-cache.json`
 * manifest and skips pages whose inputs are unchanged. Skipped pages are
 * reconstructed from the cache, so plugins (and the index) still see the full
 * page set while avoiding re-parsing and re-rendering.
 */
export function buildSite(options: BuildOptions): Site {
  const { context, pipeline } = createEngine(options);

  pipeline.runSync('onStart');
  pipeline.runSync('beforeBuild');

  const files = listMarkdownFiles(context.contentDir).sort();

  const cacheFile = options.cacheFile
    ? path.resolve(options.cacheFile)
    : path.join(context.outputDir, CACHE_FILENAME);

  const incremental = options.incremental === true && options.clean !== true;
  const manifest = incremental ? loadManifest(cacheFile) : defaultManifest();

  const startedAt = Date.now();
  const pages: Page[] = [];
  const nextManifest: CacheManifest = { version: manifest.version, pages: {} };

  let built = 0;
  let skipped = 0;

  for (const file of files) {
    const slug = deriveSlug(file, context.contentDir);
    const sourceHash = hashFile(file) ?? '';
    const cached = manifest.pages[slug];
    const sourceUnchanged = cached !== undefined && cached.sourceHash === sourceHash;

    let templateName: string | undefined;
    let layoutName: string | false | undefined;
    if (sourceUnchanged) {
      templateName = cached.template;
      layoutName = cached.layout;
    } else {
      const raw = fs.readFileSync(file, 'utf8');
      const { data } = splitFrontmatter(raw);
      templateName = typeof data.template === 'string' ? data.template : undefined;
      layoutName = data.layout;
    }

    const templateHash = computeTemplateHash(context.options, templateName, layoutName);
    const outFile = path.join(context.outputDir, `${slug}.html`);

    const skip =
      incremental &&
      sourceUnchanged &&
      cached.templateHash === templateHash &&
      fs.existsSync(outFile);

    if (skip) {
      pages.push(pageFromCache(cached, slug, file));
      nextManifest.pages[slug] = cached;
      skipped++;
    } else {
      const page: Page = {
        slug,
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
      pages.push(page);
      nextManifest.pages[slug] = {
        sourceHash,
        templateHash,
        title: page.title,
        date: page.date,
        tags: page.tags,
        html: page.html,
        frontmatter: page.frontmatter,
        template: page.template,
        layout: page.layout,
      };
      built++;
    }
  }

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

  saveManifest(cacheFile, nextManifest);

  pipeline.runSync('onEnd');

  const elapsed = Date.now() - startedAt;
  const total = built + skipped;
  const timeSavedMs = total > 0 ? Math.round((elapsed / total) * skipped) : 0;

  return {
    pages,
    outputDir: context.outputDir,
    stats: { built, skipped, timeSavedMs },
  };
}

function pageFromCache(entry: CacheEntry, slug: string, file: string): Page {
  return {
    slug,
    title: entry.title,
    date: entry.date,
    tags: entry.tags,
    html: entry.html,
    sourcePath: file,
    frontmatter: entry.frontmatter,
    template: entry.template,
    layout: entry.layout,
    cached: true,
  };
}
