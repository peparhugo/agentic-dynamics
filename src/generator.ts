import * as fs from 'fs';
import * as path from 'path';
import { parseMarkdown } from './parser';
import { renderIndex, renderPage } from './templates';
import { BuildOptions, BuildResult, Page } from './types';

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

function writeFile(filePath: string, contents: string) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, contents, 'utf-8');
}

const DEFAULT_STYLESHEET = `body { font-family: sans-serif; max-width: 40rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; }
header { margin-bottom: 2rem; }
.page-list { list-style: none; padding: 0; }
.page-list li { margin-bottom: 0.5rem; }
.tags { list-style: none; padding: 0; display: flex; gap: 0.5rem; }
.tags li { background: #eee; border-radius: 0.25rem; padding: 0.1rem 0.5rem; font-size: 0.85rem; }
`;

export function buildSite(options: BuildOptions): BuildResult {
  const { contentDir, outputDir } = options;

  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }

  const pages = loadPages(contentDir);

  fs.mkdirSync(outputDir, { recursive: true });

  for (const page of pages) {
    writeFile(path.join(outputDir, page.outputFile), renderPage(page));
  }

  writeFile(path.join(outputDir, 'index.html'), renderIndex(pages));
  writeFile(path.join(outputDir, 'style.css'), DEFAULT_STYLESHEET);

  return { pages, outputDir };
}
