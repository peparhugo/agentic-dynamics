import * as fs from 'fs';
import * as path from 'path';
import { BuildOptions, Page, markdownToHtml, normalizeTags, parseFrontmatter } from './ssg';
import { TemplateEngine } from './template-engine';

function slugFromFilename(filename: string): string {
  const ext = path.extname(filename);
  return filename.slice(0, filename.length - ext.length);
}

/** Recursively collect all .md file paths under a directory, sorted by path. */
export function findMarkdownFiles(contentDir: string): string[] {
  const results: string[] = [];

  function walk(dir: string): void {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
        results.push(full);
      }
    }
  }

  if (fs.existsSync(contentDir)) {
    walk(contentDir);
  }
  return results;
}

export function loadPages(contentDir: string): Page[] {
  const files = findMarkdownFiles(contentDir);
  const pages: Page[] = [];

  for (const file of files) {
    const raw = fs.readFileSync(file, 'utf8');
    const { frontmatter, content } = parseFrontmatter(raw);
    const html = markdownToHtml(content);
    const slug = slugFromFilename(path.basename(file));
    pages.push({
      slug,
      title: frontmatter.title || slug,
      date: frontmatter.date,
      tags: normalizeTags(frontmatter.tags),
      html,
      template: frontmatter.template,
      layout: frontmatter.layout,
      frontmatter,
    });
  }

  return pages.sort((a, b) => {
    const ad = a.date || '';
    const bd = b.date || '';
    if (ad === bd) {
      return a.title.localeCompare(b.title);
    }
    return ad < bd ? 1 : -1;
  });
}

export interface BuildResult {
  outputDir: string;
  writtenFiles: string[];
}

export function build(options: BuildOptions): BuildResult {
  const { contentDir, outputDir, templatesDir } = options;
  const pages = loadPages(contentDir);
  const engine = new TemplateEngine({ templatesDir });

  fs.mkdirSync(outputDir, { recursive: true });

  const writtenFiles: string[] = [];

  const indexHtml = engine.renderIndex(pages);
  const indexPath = path.join(outputDir, 'index.html');
  fs.writeFileSync(indexPath, indexHtml, 'utf8');
  writtenFiles.push(indexPath);

  for (const page of pages) {
    const pageHtml = engine.renderPage(page);
    const pagePath = path.join(outputDir, `${page.slug}.html`);
    fs.writeFileSync(pagePath, pageHtml, 'utf8');
    writtenFiles.push(pagePath);
  }

  return { outputDir, writtenFiles };
}
