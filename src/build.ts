import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { relative, dirname, extname, join, resolve, sep } from 'node:path';
import { MarkdownPlugin, TemplatePlugin } from './builtin-plugins';
import { loadConfiguredPlugins, runHook } from './plugins';
import { renderIndex } from './render';
import { BuildContext, BuildPage, Page, Plugin } from './types';

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? markdownFiles(path) : Promise.resolve(/\.md$/i.test(entry.name) ? [path] : []);
  }));
  return files.flat();
}

export async function buildSite(contentDirectory = './content', outputDirectory = './dist', templatesDirectory = './templates', plugins?: Plugin[]): Promise<Page[]> {
  const contentRoot = resolve(contentDirectory);
  const outputRoot = resolve(outputDirectory);
  const configuredPlugins = plugins ?? loadConfiguredPlugins();
  const pipeline = configuredPlugins.length ? configuredPlugins : [MarkdownPlugin, TemplatePlugin];
  const context: BuildContext = { contentDirectory: contentRoot, outputDirectory: outputRoot, templatesDirectory: resolve(templatesDirectory), pages: [] };

  await runHook(context, pipeline, 'onStart');
  try {
    await runHook(context, pipeline, 'beforeBuild');
    const sourceFiles = await markdownFiles(contentRoot);
    for (const sourceFile of sourceFiles) {
      const relativePath = relative(contentRoot, sourceFile);
      const page: BuildPage = {
        sourceFile,
        source: await readFile(sourceFile, 'utf8'),
        metadata: { title: '', tags: [] },
        html: '',
        outputPath: relativePath.slice(0, -extname(relativePath).length).split(sep).join('/') + '.html',
      };
      for (const plugin of pipeline) await plugin.onFile?.(page, context);
      context.pages.push(page);
    }

    context.pages.sort((left, right) => (right.metadata.date ?? '').localeCompare(left.metadata.date ?? '') || left.metadata.title.localeCompare(right.metadata.title));
    await rm(outputRoot, { recursive: true, force: true });
    await mkdir(outputRoot, { recursive: true });
    await Promise.all(context.pages.map(async (page) => {
      const destination = join(outputRoot, page.outputPath);
      await mkdir(dirname(destination), { recursive: true });
      await writeFile(destination, page.renderedHtml ?? page.html, 'utf8');
    }));
    await writeFile(join(outputRoot, 'index.html'), renderIndex(context.pages), 'utf8');
    await runHook(context, pipeline, 'afterBuild');
    return context.pages;
  } finally {
    await runHook(context, pipeline, 'onEnd');
  }
}
