import path from 'path';
import { readMarkdownFiles } from './files';
import { processMarkdownFile } from './page';
import { generatePageHtml, generateIndexHtml } from './generator';
import { PluginManager, PluginContext } from './plugin';
import { TemplatePlugin } from './plugins/template.plugin';
import { MarkdownPlugin } from './plugins/markdown.plugin';
import { CacheManager, BuildStats } from './cache';
import { loadTemplate, loadLayout, getEngine, loadPartials } from './template';

export interface BuildOptions {
  incremental?: boolean;
  clean?: boolean;
}

export async function build(
  contentDir: string,
  outputDir: string,
  templateDir?: string,
  usePlugins = false,
  options: BuildOptions = {}
): Promise<BuildStats | void> {
  console.log(`Reading markdown files from: ${contentDir}`);
  const files = await readMarkdownFiles(contentDir);

  if (files.length === 0) {
    console.log('No markdown files found.');
    return;
  }

  console.log(`Found ${files.length} markdown file(s).`);

  const cacheManager = new CacheManager(outputDir);

  if (options.clean) {
    cacheManager.clear();
    console.log('Cache cleared.');
  } else if (options.incremental) {
    await cacheManager.load();
  }

  const context: PluginContext = { contentDir, outputDir, templateDir };
  const pluginManager = new PluginManager();

  if (usePlugins) {
    pluginManager.register(MarkdownPlugin);
    pluginManager.register(TemplatePlugin);
    await pluginManager.runOnStart(context);
    await pluginManager.runBeforeBuild(context);
  }

  const pages = [];
  const skippedSlugs = new Set<string>();

  for (const file of files) {
    const page = await processMarkdownFile(file.name, file.content);
    pages.push(page);

    if (options.incremental) {
      let templateContent: string | undefined;
      let layoutContent: string | undefined;

      if (templateDir && page.template) {
        try {
          templateContent = await loadTemplate(page.template, templateDir);
        } catch (e) {
          // Template not found, will be built
        }
      }

      if (templateDir && page.layout) {
        try {
          layoutContent = await loadLayout(page.layout, templateDir);
        } catch (e) {
          // Layout not found, will be built
        }
      }

      const buildStartTime = Date.now();
      const isChanged = await cacheManager.isPageChanged(
        page.slug,
        file.content,
        templateContent,
        layoutContent
      );

      if (!isChanged) {
        skippedSlugs.add(page.slug);
        console.log(`⊘ Skipped ${page.slug}.html (unchanged)`);
        const buildTime = Date.now() - buildStartTime;
        cacheManager.recordPageBuildTime(page.slug, buildTime);
        continue;
      }
    }

    const buildStartTime = Date.now();
    await generatePageHtml(page, outputDir, templateDir, usePlugins ? pluginManager : undefined);
    const buildTime = Date.now() - buildStartTime;
    cacheManager.recordPageBuildTime(page.slug, buildTime);
    console.log(`✓ Generated ${page.slug}.html`);

    if (options.incremental) {
      const cachedHtml = await generatePageHtmlForCache(page, outputDir, templateDir, usePlugins ? pluginManager : undefined);
      let templateContent: string | undefined;
      let layoutContent: string | undefined;

      if (templateDir && page.template) {
        try {
          templateContent = await loadTemplate(page.template, templateDir);
        } catch (e) {
          // ignored
        }
      }

      if (templateDir && page.layout) {
        try {
          layoutContent = await loadLayout(page.layout, templateDir);
        } catch (e) {
          // ignored
        }
      }

      cacheManager.updateEntry(page.slug, file.content, cachedHtml, templateContent, layoutContent);
    }
  }

  await generateIndexHtml(pages, outputDir);
  console.log(`✓ Generated index.html`);

  if (usePlugins) {
    await pluginManager.runAfterBuild(pages, context);
    await pluginManager.runOnEnd(context);
  }

  if (options.incremental) {
    await cacheManager.save();
    const stats = cacheManager.getStats(files.length, skippedSlugs);
    reportBuildStats(stats);
    return stats;
  }

  console.log(`\nBuild complete! Output: ${outputDir}`);
}

async function generatePageHtmlForCache(
  page: any,
  outputDir: string,
  templateDir?: string,
  pluginManager?: PluginManager
): Promise<string> {
  if (pluginManager) {
    const context: PluginContext = { contentDir: '', outputDir, templateDir };
    const processedPage = await pluginManager.runOnFile(page, context);
    return processedPage.html;
  } else if (templateDir && page.template) {
    await loadPartials(templateDir);
    const eng = getEngine();
    let html = page.html;
    const templateContent = await loadTemplate(page.template, templateDir);
    html = eng.render(templateContent, { ...page, body: page.html });
    if (page.layout) {
      const layout = await loadLayout(page.layout, templateDir);
      html = eng.render(layout, { ...page, body: html });
    }
    return html;
  }
  return page.html;
}

function reportBuildStats(stats: BuildStats): void {
  console.log(`\nBuild Statistics:`);
  console.log(`  Pages built:   ${stats.pagesBuilt}`);
  console.log(`  Pages skipped: ${stats.pagesSkipped}`);
  console.log(`  Total pages:   ${stats.totalPages}`);
  if (stats.timeSaved > 0) {
    console.log(`  Time saved:    ${stats.timeSaved}ms`);
  }
  console.log(`\nBuild complete! Output: ${stats.totalPages === stats.pagesBuilt ? 'Full build' : 'Incremental build'} done.`);
}
