import fs from 'fs';
import { Plugin } from '../plugin';
import { Page } from '../types';
import { parseMarkdown, normalizeTags, defaultTitle } from '../markdown';

/**
 * Built-in plugin that parses raw markdown (with optional frontmatter) into
 * the page's HTML and metadata. Registered on the `onFile` hook so it runs for
 * every discovered markdown file.
 */
export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  onFile(page: Page): void {
    const raw = fs.readFileSync(page.sourcePath, 'utf8');
    const { frontmatter, html } = parseMarkdown(raw);

    page.html = html;
    page.frontmatter = frontmatter;
    page.title = frontmatter.title ?? defaultTitle(page.slug);
    page.date = frontmatter.date != null ? String(frontmatter.date) : undefined;
    page.tags = normalizeTags(frontmatter.tags);
    page.template = typeof frontmatter.template === 'string' ? frontmatter.template : undefined;
    page.layout = frontmatter.layout;
  }
}
