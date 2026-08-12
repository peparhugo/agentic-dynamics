import fs from 'fs';
import path from 'path';
import { parseMarkdownFile } from './parser';
import { TemplateEngine, renderIndex } from './template';
import { Page } from './types';

const DEFAULT_CONTENT_DIR = 'content';
const DEFAULT_OUTPUT_DIR = 'dist';
const DEFAULT_TEMPLATE_DIR = 'templates';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
}

function collectMarkdownFiles(dir: string): string[] {
  const results: string[] = [];
  if (!fs.existsSync(dir)) {
    return results;
  }
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  entries.sort((a, b) => a.name.localeCompare(b.name));
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectMarkdownFiles(fullPath));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
      results.push(fullPath);
    }
  }
  return results;
}

function ensureCleanDir(dir: string): void {
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
}

export function build(options: BuildOptions = {}): Page[] {
  const contentDir = path.resolve(options.contentDir ?? DEFAULT_CONTENT_DIR);
  const outputDir = path.resolve(options.outputDir ?? DEFAULT_OUTPUT_DIR);
  const templateDir = path.resolve(options.templateDir ?? DEFAULT_TEMPLATE_DIR);

  const files = collectMarkdownFiles(contentDir);
  const pages = files.map((file) => parseMarkdownFile(file, contentDir));

  const engine = new TemplateEngine({
    templateDir,
    defaultTemplate: options.defaultTemplate,
    defaultLayout: options.defaultLayout,
  });

  ensureCleanDir(outputDir);

  for (const page of pages) {
    const fileName = `${page.slug}.html`;
    const filePath = path.join(outputDir, fileName);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, engine.renderPage(page), 'utf8');
  }

  fs.writeFileSync(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');

  return pages;
}
