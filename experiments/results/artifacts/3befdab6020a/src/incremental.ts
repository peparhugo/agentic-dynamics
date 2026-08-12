import fs from 'fs';
import path from 'path';
import { Page, BuildStats } from './types';
import { TemplateEngine } from './templates';
import { CacheManager } from './cache';

export function generateSiteIncremental(
  pages: Page[],
  outputDir: string,
  contentDir: string,
  templatesDir: string,
  clean: boolean = false
): BuildStats {
  const resolvedOutput = path.resolve(outputDir);
  fs.mkdirSync(resolvedOutput, { recursive: true });

  const cache = new CacheManager(resolvedOutput);

  if (clean) {
    cache.clear();
  }

  cache.load();

  const templatesHash = CacheManager.computeTemplateHashes(templatesDir);

  const engine = new TemplateEngine(templatesDir);

  const knownSlugs = pages.map((p) => p.slug);
  const prunedCount = cache.prune(knownSlugs);

  let pagesBuilt = 0;
  let pagesSkipped = 0;

  for (const page of pages) {
    const sourcePath = path.join(path.resolve(contentDir), `${page.slug}.md`);
    const sourceHash = CacheManager.computeFileHash(sourcePath);

    if (cache.isStale(page.slug, sourceHash, templatesHash)) {
      const body = engine.renderPage(page);
      const html = engine.renderLayout(page.frontmatter.title, body, page.frontmatter.layout);
      fs.writeFileSync(path.join(resolvedOutput, `${page.slug}.html`), html, 'utf-8');
      cache.update(page.slug, sourceHash, templatesHash);
      pagesBuilt++;
    } else {
      pagesSkipped++;
    }
  }

  const indexSourcePath = path.join(resolvedOutput, 'index.html');
  const needsIndexRebuild = pagesBuilt > 0 || prunedCount > 0 || pagesSkipped === 0 || !fs.existsSync(indexSourcePath);

  if (needsIndexRebuild) {
    const indexBody = engine.renderIndex(pages);
    const indexHtml = engine.renderLayout('Site Index', indexBody);
    fs.writeFileSync(indexSourcePath, indexHtml, 'utf-8');
    pagesBuilt++;
  } else {
    pagesSkipped++;
  }

  cache.save();

  return {
    pagesBuilt,
    pagesSkipped,
    totalPages: pages.length + 1,
  };
}
