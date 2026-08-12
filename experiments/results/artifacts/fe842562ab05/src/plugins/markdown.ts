import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { hashFile } from '../cache';
import type { Plugin } from '../plugin';
import type { Page, PageMetadata } from '../generator';

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(file));
    else if (entry.isFile() && path.extname(entry.name).toLowerCase() === '.md') files.push(file);
  }
  return files.sort();
}

export class MarkdownPlugin implements Plugin {
  async beforeBuild(context: Parameters<NonNullable<Plugin['beforeBuild']>>[0]): Promise<void> {
    const sources = await markdownFiles(context.contentDir);
    context.pages.push(...await Promise.all(sources.map(async (sourcePath): Promise<Page> => {
      const relativePath = path.relative(context.contentDir, sourcePath);
      const sourceHash = await hashFile(sourcePath);
      const cached = context.cache?.parsed.get(relativePath);
      let metadata: PageMetadata;
      let content: string;
      if (cached?.sourceHash === sourceHash) {
        metadata = cached.metadata;
        content = cached.content;
      } else {
        const parsed = matter(await readFile(sourcePath, 'utf8'));
        const rawTags = parsed.data.tags;
        const tags = Array.isArray(rawTags)
          ? rawTags.map(String)
          : typeof rawTags === 'string' ? rawTags.split(',').map((tag) => tag.trim()).filter(Boolean) : [];
        metadata = { ...parsed.data, tags } as PageMetadata;
        content = await marked.parse(parsed.content);
      }
      const outputRelativePath = relativePath.replace(/\.md$/i, '.html');
      return {
        sourcePath,
        outputPath: path.join(context.outputDir, outputRelativePath),
        url: `/${outputRelativePath.split(path.sep).join('/')}`,
        metadata,
        content
      };
    })));
    context.pages.sort((a, b) => String(a.metadata.title || path.basename(a.sourcePath, path.extname(a.sourcePath)))
      .localeCompare(String(b.metadata.title || path.basename(b.sourcePath, path.extname(b.sourcePath)))));
  }
}

export default MarkdownPlugin;
