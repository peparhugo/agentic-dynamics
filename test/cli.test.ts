import fs from 'fs';
import os from 'os';
import path from 'path';
import { buildSite, parseArgs, runCli, slugify } from '../src/cli';

const CONTENT = `---
title: First Post
date: 2024-05-10
tags: [hello, world]
---
# First Post

Welcome to the **first** post.
`;

const ABOUT = `---
title: About
date: 2023-12-01
tags: [meta]
---
All about this site.
`;

const NO_META = `# No Metadata

Plain markdown only.
`;

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
}

function writeContent(dir: string, files: Record<string, string>): void {
  fs.mkdirSync(dir, { recursive: true });
  for (const [name, contents] of Object.entries(files)) {
    fs.writeFileSync(path.join(dir, name), contents, 'utf-8');
  }
}

function read(dir: string, file: string): string {
  return fs.readFileSync(path.join(dir, file), 'utf-8');
}

function cleanup(dir: string): void {
  fs.rmSync(dir, { recursive: true, force: true });
}

describe('slugify', () => {
  it('lowercases and normalises file names', () => {
    expect(slugify('Hello World.md')).toBe('hello-world');
    expect(slugify('Post-Title.markdown')).toBe('post-title');
    expect(slugify('index.md')).toBe('index');
  });
});

describe('parseArgs', () => {
  it('uses defaults when no options are given', () => {
    const opts = parseArgs(['build']);
    expect(opts.command).toBe('build');
    expect(opts.contentDir).toBe('content');
    expect(opts.outputDir).toBe('dist');
  });

  it('parses --content and --output as separate arguments', () => {
    const opts = parseArgs(['build', '--content', 'posts', '--output', 'public']);
    expect(opts.contentDir).toBe('posts');
    expect(opts.outputDir).toBe('public');
  });

  it('parses --content and --output with equals syntax', () => {
    const opts = parseArgs(['build', '--content=posts', '--output=public']);
    expect(opts.contentDir).toBe('posts');
    expect(opts.outputDir).toBe('public');
  });

  it('recognises help and version commands', () => {
    expect(parseArgs(['--help']).command).toBe('help');
    expect(parseArgs(['--version']).command).toBe('version');
  });
});

describe('buildSite', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTempDir();
    outputDir = path.join(contentDir, 'dist');
  });

  afterEach(() => {
    cleanup(contentDir);
  });

  it('writes an index.html and one HTML file per page', () => {
    writeContent(contentDir, {
      'first-post.md': CONTENT,
      'about.md': ABOUT,
      'no-meta.md': NO_META,
    });

    const result = buildSite(contentDir, outputDir);

    expect(result.pages).toHaveLength(3);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'first-post.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'about.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'no-meta.html'))).toBe(true);
  });

  it('creates the output directory when it does not exist', () => {
    writeContent(contentDir, { 'about.md': ABOUT });
    const nested = path.join(contentDir, 'deep', 'nested', 'out');

    buildSite(contentDir, nested);

    expect(fs.existsSync(path.join(nested, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(nested, 'about.html'))).toBe(true);
  });

  it('renders frontmatter data into the page and strips the delimiters', () => {
    writeContent(contentDir, { 'first-post.md': CONTENT });
    buildSite(contentDir, outputDir);

    const page = read(outputDir, 'first-post.html');
    expect(page).toContain('<title>First Post</title>');
    expect(page).toContain('<h1 class="title">First Post</h1>');
    expect(page).toContain('<h1>First Post</h1>');
    expect(page).not.toContain('---');
    expect(page).not.toContain('title: First Post');
    expect(page).toContain('<strong>first</strong>');
  });

  it('renders pages without frontmatter using the slug as the title', () => {
    writeContent(contentDir, { 'no-meta.md': NO_META });
    buildSite(contentDir, outputDir);

    const page = read(outputDir, 'no-meta.html');
    expect(page).toContain('<title>no-meta</title>');
    expect(page).toContain('<h1>No Metadata</h1>');
  });

  it('generates an index listing every page in date-descending order', () => {
    writeContent(contentDir, {
      'first-post.md': CONTENT,
      'about.md': ABOUT,
    });
    buildSite(contentDir, outputDir);

    const index = read(outputDir, 'index.html');
    const firstPost = index.indexOf('first-post.html');
    const about = index.indexOf('about.html');

    expect(index).toContain('<title>All pages</title>');
    expect(index).toContain('<a href="./first-post.html">');
    expect(index).toContain('<a href="./about.html">');
    expect(firstPost).toBeGreaterThan(0);
    expect(about).toBeGreaterThan(0);
    expect(firstPost).toBeLessThan(about);
  });

  it('maps index.md to a page file without clobbering the generated index', () => {
    writeContent(contentDir, { 'index.md': CONTENT });
    buildSite(contentDir, outputDir);

    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index-page.html'))).toBe(true);
    const page = read(outputDir, 'index-page.html');
    expect(page).toContain('<title>First Post</title>');
  });

  it('ignores non-markdown files in the content directory', () => {
    writeContent(contentDir, { 'about.md': ABOUT, 'notes.txt': 'ignored' });
    const result = buildSite(contentDir, outputDir);

    expect(result.pages).toHaveLength(1);
    expect(fs.existsSync(path.join(outputDir, 'notes.html'))).toBe(false);
  });

  it('throws when the content directory does not exist', () => {
    expect(() => buildSite(path.join(contentDir, 'missing'), outputDir)).toThrow(
      'content directory not found',
    );
  });

  it('throws when the content directory has no markdown files', () => {
    writeContent(contentDir, { 'notes.txt': 'no markdown here' });
    expect(() => buildSite(contentDir, outputDir)).toThrow('no markdown files found');
  });
});

describe('runCli', () => {
  let root: string;

  beforeEach(() => {
    root = makeTempDir();
  });

  afterEach(() => {
    cleanup(root);
  });

  it('builds the site with --content and --output and prints a summary', () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'public');
    writeContent(contentDir, { 'post.md': CONTENT });

    const code = runCli(['build', '--content', contentDir, '--output', outputDir]);

    expect(code).toBe(0);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'post.html'))).toBe(true);
  });

  it('returns a non-zero exit code when the content directory is missing', () => {
    const code = runCli(['build', '--content', path.join(root, 'nope'), '--output', path.join(root, 'out')]);
    expect(code).toBe(1);
  });

  it('returns a non-zero exit code for unknown commands', () => {
    expect(runCli(['frobnicate'])).toBe(1);
  });

  it('returns zero for --help and --version', () => {
    expect(runCli(['--help'])).toBe(0);
    expect(runCli(['--version'])).toBe(0);
  });
});
