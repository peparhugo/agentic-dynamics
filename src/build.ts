import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { relative, basename, dirname, extname, join, resolve, sep } from 'node:path';
import { parseMarkdown } from './markdown';
import { renderIndex, renderPage } from './render';
import { Page } from './types';

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? markdownFiles(path) : Promise.resolve(/\.md$/i.test(entry.name) ? [path] : []);
  }));
  return files.flat();
}

export async function buildSite(contentDirectory = './content', outputDirectory = './dist'): Promise<Page[]> {
  const contentRoot = resolve(contentDirectory);
  const outputRoot = resolve(outputDirectory);
  const sourceFiles = await markdownFiles(contentRoot);
  const pages = await Promise.all(sourceFiles.map(async (sourceFile): Promise<Page> => {
    const relativePath = relative(contentRoot, sourceFile);
    const outputPath = relativePath.slice(0, -extname(relativePath).length).split(sep).join('/') + '.html';
    const source = await readFile(sourceFile, 'utf8');
    const { metadata, html } = parseMarkdown(source, basename(sourceFile, extname(sourceFile)));
    return { metadata, html, outputPath };
  }));

  pages.sort((left, right) => (right.metadata.date ?? '').localeCompare(left.metadata.date ?? '') || left.metadata.title.localeCompare(right.metadata.title));
  await rm(outputRoot, { recursive: true, force: true });
  await mkdir(outputRoot, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    const destination = join(outputRoot, page.outputPath);
    await mkdir(dirname(destination), { recursive: true });
    await writeFile(destination, renderPage(page.metadata, page.html), 'utf8');
  }));
  await writeFile(join(outputRoot, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
