import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { generateSite } from '../src/generator.js';
import { parseMarkdownFiles } from '../src/parser.js';
import { join } from 'node:path';
import { mkdtemp, rm, readFile, access } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import type { SiteConfig } from '../src/types.js';

const fixturesDir = join(import.meta.dirname, 'fixtures');
const sourceDir = join(fixturesDir, 'source');
const templateDir = join(fixturesDir, 'templates');

describe('generateSite', () => {
  let outputDir: string;

  beforeEach(async () => {
    outputDir = await mkdtemp(join(tmpdir(), 'ssg-out-'));
  });

  afterEach(async () => {
    await rm(outputDir, { recursive: true, force: true });
  });

  const config: SiteConfig = {
    sourceDir,
    templateDir,
    outputDir: '', // set in beforeEach
    siteTitle: 'Test Site',
    siteUrl: 'https://example.com',
    siteDescription: 'A test site',
  };

  it('generates HTML pages from markdown', async () => {
    config.outputDir = outputDir;
    const pages = await parseMarkdownFiles(sourceDir);
    await generateSite(pages, config);

    const post1 = await readFile(join(outputDir, 'post1.html'), 'utf-8');
    expect(post1).toContain('<!DOCTYPE html>');
    expect(post1).toContain('First Post');
    expect(post1).toContain('<h1>Hello World</h1>');
  });

  it('renders with layout including partials', async () => {
    config.outputDir = outputDir;
    const pages = await parseMarkdownFiles(sourceDir);
    await generateSite(pages, config);

    const post1 = await readFile(join(outputDir, 'post1.html'), 'utf-8');
    expect(post1).toContain('<nav><a href="/">Home</a></nav>');
    expect(post1).toContain('&copy; Test Site');
  });

  it('renders index page', async () => {
    config.outputDir = outputDir;
    const pages = await parseMarkdownFiles(sourceDir);
    await generateSite(pages, config);

    const index = await readFile(join(outputDir, 'index.html'), 'utf-8');
    expect(index).toContain('<a href="/post1.html">First Post</a>');
    expect(index).toContain('<a href="/post2.html">Second Post</a>');
  });

  it('generates tag pages', async () => {
    config.outputDir = outputDir;
    const pages = await parseMarkdownFiles(sourceDir);
    await generateSite(pages, config);

    const tutorialTag = await readFile(
      join(outputDir, 'tags', 'tutorial.html'),
      'utf-8',
    );
    expect(tutorialTag).toContain('<a href="/post1.html">First Post</a>');
    expect(tutorialTag).toContain('<a href="/post2.html">Second Post</a>');

    const jsTag = await readFile(
      join(outputDir, 'tags', 'javascript.html'),
      'utf-8',
    );
    expect(jsTag).toContain('First Post');
    expect(jsTag).not.toContain('Second Post');
  });

  it('generates RSS feed when siteUrl is set', async () => {
    config.outputDir = outputDir;
    const pages = await parseMarkdownFiles(sourceDir);
    await generateSite(pages, config);

    const feed = await readFile(join(outputDir, 'feed.xml'), 'utf-8');
    expect(feed).toContain('<rss version="2.0"');
    expect(feed).toContain('<title>First Post</title>');
    expect(feed).toContain('<link>https://example.com/post1.html</link>');
  });

  it('does not generate RSS feed without siteUrl', async () => {
    config.outputDir = outputDir;
    config.siteUrl = undefined;
    const pages = await parseMarkdownFiles(sourceDir);
    await generateSite(pages, config);

    await expect(
      access(join(outputDir, 'feed.xml')),
    ).rejects.toThrow();
  });

  it('includes tags in page output', async () => {
    config.outputDir = outputDir;
    const pages = await parseMarkdownFiles(sourceDir);
    await generateSite(pages, config);

    const post1 = await readFile(join(outputDir, 'post1.html'), 'utf-8');
    expect(post1).toContain('<a href="/tags/javascript.html">javascript</a>');
    expect(post1).toContain('<a href="/tags/tutorial.html">tutorial</a>');
  });

  it('treats page template as optional', async () => {
    const tmpTemplate = await mkdtemp(join(tmpdir(), 'ssg-tmpl-'));
    try {
      // Only layout, no page.hbs
      await import('node:fs/promises').then((fs) =>
        fs.writeFile(
          join(tmpTemplate, 'layout.hbs'),
          '<html><body>Layout: {{{body}}}</body></html>',
        ),
      );

      const cfg = { ...config, templateDir: tmpTemplate, outputDir };
      const pages = await parseMarkdownFiles(sourceDir);
      await generateSite(pages, cfg);
      // should not throw
    } finally {
      await rm(tmpTemplate, { recursive: true, force: true });
    }
  });
});
