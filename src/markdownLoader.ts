import * as fs from 'fs';
import * as path from 'path';
import { parseMarkdown } from './parser';
import { Page } from './types';

const MARKDOWN_EXTENSIONS = new Set(['.md', '.markdown']);

/**
 * Recursively finds markdown files under `dir`, returning paths relative to
 * `dir` (using forward slashes).
 */
export function findMarkdownFiles(dir: string): string[] {
  const results: string[] = [];

  function walk(current: string) {
    const entries = fs.readdirSync(current, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (MARKDOWN_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) {
        results.push(path.relative(dir, fullPath).split(path.sep).join('/'));
      }
    }
  }

  if (fs.existsSync(dir)) {
    walk(dir);
  }

  return results;
}

export function loadPages(contentDir: string): Page[] {
  const files = findMarkdownFiles(contentDir);
  return files.map((relativePath) => {
    const raw = fs.readFileSync(path.join(contentDir, relativePath), 'utf-8');
    return parseMarkdown(raw, relativePath);
  });
}
