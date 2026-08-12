#!/usr/bin/env node
import fs from 'fs';
import path from 'path';
import { parseMarkdown, renderMarkdown } from './parser';
import { buildPageHtml, buildIndexHtml, pageTitle } from './generator';
import { TemplateEngine } from './engine';
import type { SiteContext } from './engine';
import type { Page } from './types';

export interface CliOptions {
  command: string;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
}

export interface SiteBuildResult {
  outputDir: string;
  pages: Page[];
  indexFile: string;
}

const HELP = `ssg — a tiny static site generator

Usage:
  ssg build [options]

Options:
  --content <dir>    Directory containing Markdown files (default: ./content)
  --output <dir>     Directory where the site is written (default: ./dist)
  --templates <dir>  Directory containing Handlebars templates (default: ./templates)
  --help             Show this help message
  --version          Show the version number
`;

const VERSION = '1.0.0';

export function parseArgs(argv: string[]): CliOptions {
  let command = '';
  let contentDir = 'content';
  let outputDir = 'dist';
  let templatesDir = 'templates';

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--content') {
      contentDir = argv[++i];
    } else if (arg.startsWith('--content=')) {
      contentDir = arg.slice('--content='.length);
    } else if (arg === '--output') {
      outputDir = argv[++i];
    } else if (arg.startsWith('--output=')) {
      outputDir = arg.slice('--output='.length);
    } else if (arg === '--templates') {
      templatesDir = argv[++i];
    } else if (arg.startsWith('--templates=')) {
      templatesDir = arg.slice('--templates='.length);
    } else if (arg === '--help' || arg === '-h') {
      command = 'help';
    } else if (arg === '--version' || arg === '-v') {
      command = 'version';
    } else {
      command = arg;
    }
  }

  if (!command) {
    command = 'build';
  }

  return { command, contentDir, outputDir, templatesDir };
}

export function slugify(fileName: string): string {
  const slug = fileName
    .toLowerCase()
    .replace(/\.[^.]+$/, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug || 'page';
}

export function buildSite(
  contentDir: string,
  outputDir: string,
  templatesDir = 'templates',
): SiteBuildResult {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`content directory not found: ${contentDir}`);
  }

  const mdFiles = fs
    .readdirSync(contentDir)
    .filter((f) => {
      if (!fs.statSync(path.join(contentDir, f)).isFile()) return false;
      return f.toLowerCase().endsWith('.md');
    })
    .sort();

  if (mdFiles.length === 0) {
    throw new Error(`no markdown files found in: ${contentDir}`);
  }

  fs.mkdirSync(outputDir, { recursive: true });

  const pages: Page[] = mdFiles.map((file) => {
    const raw = fs.readFileSync(path.join(contentDir, file), 'utf-8');
    const { data, body } = parseMarkdown(raw);
    const slug = slugify(file);
    return {
      slug,
      sourcePath: file,
      data,
      body,
      html: renderMarkdown(body),
      outputFile: slug === 'index' ? 'index-page.html' : `${slug}.html`,
    };
  });

  pages.sort((a, b) => {
    const dateA = a.data.date ? String(a.data.date) : '';
    const dateB = b.data.date ? String(b.data.date) : '';
    if (dateA !== dateB) {
      return dateA > dateB ? -1 : 1;
    }
    return a.slug.localeCompare(b.slug);
  });

  const engine = fs.existsSync(templatesDir) ? new TemplateEngine(templatesDir) : null;
  const site: SiteContext = {
    pages: pages.map((page) => ({
      slug: page.slug,
      title: pageTitle(page.data, page.slug),
      outputFile: page.outputFile,
      date: page.data.date !== undefined ? String(page.data.date) : undefined,
    })),
  };

  for (const page of pages) {
    const templated = engine ? engine.renderPage(page, site) : null;
    const html = templated !== null ? templated : buildPageHtml(page);
    fs.writeFileSync(path.join(outputDir, page.outputFile), html, 'utf-8');
  }

  const indexFile = path.join(outputDir, 'index.html');
  fs.writeFileSync(indexFile, buildIndexHtml(pages), 'utf-8');

  return { outputDir, pages, indexFile };
}

export function runCli(argv: string[]): number {
  const options = parseArgs(argv);

  if (options.command === 'help') {
    process.stdout.write(HELP);
    return 0;
  }
  if (options.command === 'version') {
    process.stdout.write(`${VERSION}\n`);
    return 0;
  }
  if (options.command !== 'build') {
    process.stderr.write(`ssg: unknown command "${options.command}"\n\nRun "ssg --help" for usage.\n`);
    return 1;
  }

  try {
    const result = buildSite(options.contentDir, options.outputDir, options.templatesDir);
    process.stdout.write(`Generated ${result.pages.length} page(s) in ${result.outputDir}\n`);
    return 0;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    process.stderr.write(`ssg: build failed: ${message}\n`);
    return 1;
  }
}

if (require.main === module) {
  process.exitCode = runCli(process.argv.slice(2));
}
