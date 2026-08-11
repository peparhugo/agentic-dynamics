import fs from 'fs';
import path from 'path';
import { Plugin, BuildOptions, loadPluginsFromConfig } from './plugin';
import { parseMarkdownFile, readContentDirectory, MarkdownPlugin } from './plugins/markdown';
import { renderPage, renderIndex, TemplatePlugin } from './plugins/template';
import { TemplateEngine } from './templates';
import { BuildCache } from './cache';

export { parseMarkdownFile, readContentDirectory } from './plugins/markdown';

function scanContentFiles(contentDir: string): { name: string; fullPath: string }[] {
  if (!fs.existsSync(contentDir)) return [];
  return fs.readdirSync(contentDir)
    .filter((e) => e.endsWith('.md'))
    .map((name) => ({ name, fullPath: path.join(contentDir, name) }));
}

export function generateSite(
  contentDir: string,
  outputDir: string,
  templatesDir?: string,
  buildOpts?: { incremental?: boolean; clean?: boolean }
): number {
  const incremental = buildOpts?.incremental ?? false;
  const clean = buildOpts?.clean ?? false;

  const plugins: Plugin[] = [
    new MarkdownPlugin(),
    new TemplatePlugin(),
    ...loadPluginsFromConfig(),
  ];

  const options: BuildOptions = { contentDir, outputDir, templatesDir, incremental, clean };

  for (const p of plugins) if (p.onStart) p.onStart();
  for (const p of plugins) if (p.beforeBuild) p.beforeBuild(options);

  const contentFiles = scanContentFiles(contentDir);

  if (contentFiles.length === 0) {
    console.log(`No markdown files found in ${contentDir}`);
    for (const p of plugins) if (p.onEnd) p.onEnd();
    return 0;
  }

  fs.mkdirSync(outputDir, { recursive: true });

  const engine = templatesDir ? new TemplateEngine(templatesDir) : null;
  const useTemplates = engine && engine.initialized;

  const cache = new BuildCache(contentDir, outputDir, templatesDir);

  if (clean) {
    cache.clear();
  } else if (incremental) {
    cache.load();
  }

  let builtCount = 0;
  let skippedCount = 0;
  const allPages = [];
  const knownSlugs = new Set<string>();

  for (const file of contentFiles) {
    let page = parseMarkdownFile(file.fullPath);
    if (!page) continue;

    knownSlugs.add(page.slug);

    if (incremental && cache.shouldSkipFile(file.fullPath, page.slug)) {
      skippedCount++;
      allPages.push(page);
      continue;
    }

    builtCount++;

    for (const p of plugins) {
      if (p.onFile) page = p.onFile(page);
    }

    const html = useTemplates
      ? (engine!.render(page) || renderPage(page))
      : renderPage(page);

    cache.cacheHtml(page.slug, html);
    fs.writeFileSync(path.join(outputDir, `${page.slug}.html`), html);

    allPages.push(page);
    cache.updateManifest(file.fullPath, page.slug);
  }

  cache.removeStaleEntries(knownSlugs);

  const indexHtml = useTemplates
    ? (engine!.renderIndex(allPages) || renderIndex(allPages))
    : renderIndex(allPages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml);
  builtCount++; // index always counts as built

  const indexFileCount = 1;

  cache.stats = {
    totalPages: builtCount + skippedCount,
    pagesBuilt: builtCount,
    pagesSkipped: skippedCount,
    timeSaved: '0ms',
  };

  if (incremental) {
    cache.finalize();
    cache.persist();
    cache.reportStats();
  }

  for (const p of plugins) if (p.afterBuild) p.afterBuild(options);
  for (const p of plugins) if (p.onEnd) p.onEnd();

  const total = contentFiles.length + indexFileCount;
  console.log(`Generated ${total} files in ${outputDir}`);
  return total;
}
