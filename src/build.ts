import { promises as fs } from 'fs';
import path from 'path';
import { parseFrontmatter, normalizeTags } from './frontmatter';
import { markdownToHtml } from './markdown';
import { renderIndex, renderPage } from './render';
import { TemplateEngine } from './templates';
import type { BuildOptions, Page } from './types';

const MARKDOWN_EXT = /\.(md|markdown)$/i;

async function findMarkdownFiles(dir: string): Promise<string[]> {
  const results: string[] = [];
  let entries;
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return results;
  }

  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...(await findMarkdownFiles(full)));
    } else if (entry.isFile() && MARKDOWN_EXT.test(entry.name)) {
      results.push(full);
    }
  }
  return results;
}

function slugFor(contentDir: string, filePath: string): string {
  const relative = path.relative(contentDir, filePath);
  const withoutExt = relative.replace(MARKDOWN_EXT, '');
  return withoutExt.split(path.sep).join('/');
}

function titleFor(slug: string, data: { title?: string }): string {
  if (data.title && data.title.trim()) {
    return data.title.trim();
  }
  const segments = slug.split('/').filter(Boolean);
  return segments[segments.length - 1] ?? slug;
}

export async function build(options: BuildOptions): Promise<Page[]> {
  const contentDir = path.resolve(options.content);
  const outputDir = path.resolve(options.output);
  const templatesDir = options.templates ?? './templates';

  const engine = new TemplateEngine(templatesDir);
  await engine.load();

  const files = (await findMarkdownFiles(contentDir)).sort();

  const pages: Page[] = [];
  for (const file of files) {
    const raw = await fs.readFile(file, 'utf8');
    const { data, body } = parseFrontmatter(raw);
    const contentHtml = markdownToHtml(body);
    const slug = slugFor(contentDir, file);

    pages.push({
      slug,
      title: titleFor(slug, data),
      date: data.date,
      tags: normalizeTags(data.tags),
      contentHtml,
      sourcePath: file,
      outputPath: path.join(outputDir, `${slug}.html`),
      template: data.template,
      layout: data.layout,
      data,
    });
  }

  await fs.mkdir(outputDir, { recursive: true });

  for (const page of pages) {
    await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
    await fs.writeFile(page.outputPath, renderPage(page, engine), 'utf8');
  }

  await fs.writeFile(path.join(outputDir, 'index.html'), renderIndex(pages, engine), 'utf8');

  return pages;
}
