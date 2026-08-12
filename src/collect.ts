import fs from 'fs';
import path from 'path';
import { Page } from './types';
import { parseMarkdown } from './parse';

export function collectMarkdownFiles(contentDir: string): string[] {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory does not exist: ${contentDir}`);
  }
  const entries = fs.readdirSync(contentDir, { withFileTypes: true });
  return entries
    .filter((e) => e.isFile() && e.name.endsWith('.md'))
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((e) => path.join(contentDir, e.name));
}

export function collectPages(contentDir: string): Page[] {
  return collectMarkdownFiles(contentDir).map((file) => parseMarkdown(file));
}
