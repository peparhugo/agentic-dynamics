import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { Plugin, BuildContext } from '../plugin';
import { Page } from '../types';

function slugify(filename: string): string {
  const name = path.basename(filename, path.extname(filename));
  return name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
}

function readMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) {
    return [];
  }
  return fs.readdirSync(contentDir)
    .filter(f => f.endsWith('.md'))
    .map(f => path.join(contentDir, f));
}

function parsePage(filePath: string): Page {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);
  const html = marked.parse(content) as string;
  const slug = slugify(path.basename(filePath));
  return {
    frontmatter: {
      title: data.title || slug,
      date: data.date,
      tags: data.tags,
      template: data.template,
      layout: data.layout,
    },
    html,
    slug,
  };
}

export class MarkdownPlugin implements Plugin {
  name = 'markdown';

  beforeBuild(context: BuildContext): void {
    const { contentDir } = context.options;
    const files = readMarkdownFiles(contentDir);
    for (const file of files) {
      const page = parsePage(file);
      context.pages.push(page);
    }
  }
}
