import fs from 'fs';
import path from 'path';
import { Plugin, BuildOptions, loadPluginsFromConfig } from './plugin';
import { readContentDirectory, MarkdownPlugin } from './plugins/markdown';
import { renderPage, renderIndex, TemplatePlugin } from './plugins/template';
import { TemplateEngine } from './templates';

export { parseMarkdownFile, readContentDirectory } from './plugins/markdown';

export function generateSite(contentDir: string, outputDir: string, templatesDir?: string): number {
  const plugins: Plugin[] = [
    new MarkdownPlugin(),
    new TemplatePlugin(),
    ...loadPluginsFromConfig(),
  ];

  const options: BuildOptions = { contentDir, outputDir, templatesDir };

  for (const p of plugins) if (p.onStart) p.onStart();
  for (const p of plugins) if (p.beforeBuild) p.beforeBuild(options);

  const pages = readContentDirectory(contentDir);

  if (pages.length === 0) {
    console.log(`No markdown files found in ${contentDir}`);
    for (const p of plugins) if (p.onEnd) p.onEnd();
    return 0;
  }

  fs.mkdirSync(outputDir, { recursive: true });

  const engine = templatesDir ? new TemplateEngine(templatesDir) : null;
  const useTemplates = engine && engine.initialized;

  for (let i = 0; i < pages.length; i++) {
    let page = pages[i];
    for (const p of plugins) {
      if (p.onFile) page = p.onFile(page);
    }
    pages[i] = page;

    const html = useTemplates
      ? (engine!.render(page) || renderPage(page))
      : renderPage(page);
    fs.writeFileSync(path.join(outputDir, `${page.slug}.html`), html);
  }

  const indexHtml = useTemplates
    ? (engine!.renderIndex(pages) || renderIndex(pages))
    : renderIndex(pages);
  fs.writeFileSync(path.join(outputDir, 'index.html'), indexHtml);

  for (const p of plugins) if (p.afterBuild) p.afterBuild(options);
  for (const p of plugins) if (p.onEnd) p.onEnd();

  console.log(`Generated ${pages.length + 1} files in ${outputDir}`);
  return pages.length + 1;
}
