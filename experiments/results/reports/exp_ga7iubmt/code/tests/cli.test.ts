import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { mkdtemp, rm, readFile } from 'fs/promises';
import { join, dirname } from 'path';
import { tmpdir } from 'os';
import { fileURLToPath } from 'url';
import { build } from '../src/generator.js';
import { createProgram } from '../src/index.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURES = join(__dirname, 'fixtures');

describe('CLI program configuration', () => {
  it('has build and serve commands', () => {
    const program = createProgram();
    const commandNames = program.commands.map((c) => c.name());
    expect(commandNames).toContain('build');
    expect(commandNames).toContain('serve');
  });

  it('build command has source option', () => {
    const program = createProgram();
    const buildCmd = program.commands.find((c) => c.name() === 'build')!;
    const optionNames = buildCmd.options.map((o) => o.long);
    expect(optionNames).toContain('--source');
    expect(optionNames).toContain('--templates');
    expect(optionNames).toContain('--output');
    expect(optionNames).toContain('--include-drafts');
  });

  it('serve command has port option', () => {
    const program = createProgram();
    const serveCmd = program.commands.find((c) => c.name() === 'serve')!;
    const optionNames = serveCmd.options.map((o) => o.long);
    expect(optionNames).toContain('--port');
  });

  it('build command has default values', () => {
    const program = createProgram();
    const buildCmd = program.commands.find((c) => c.name() === 'build')!;
    const sourceOpt = buildCmd.options.find((o) => o.long === '--source')!;
    const outputOpt = buildCmd.options.find((o) => o.long === '--output')!;
    expect(sourceOpt.defaultValue).toBe('./content');
    expect(outputOpt.defaultValue).toBe('./dist');
  });
});

describe('build', () => {
  let tmpDir: string;

  beforeAll(async () => {
    tmpDir = await mkdtemp(join(tmpdir(), 'ssg-test-'));
  });

  afterAll(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  it('builds a site from fixtures', async () => {
    const outputDir = join(tmpDir, 'output');
    const sourceDir = join(FIXTURES, 'content');
    const templatesDir = join(FIXTURES, 'templates');

    await build({
      source: sourceDir,
      templates: templatesDir,
      output: outputDir,
      title: 'Test Blog',
      description: 'A test blog',
      url: 'https://test.example.com',
    });

    // Check that post page was generated
    const postHtml = await readFile(
      join(outputDir, 'post-with-tags', 'index.html'),
      'utf-8',
    );
    expect(postHtml).toContain('Hello World');
    expect(postHtml).toContain('January 15, 2024');
    expect(postHtml).toContain('javascript');
    expect(postHtml).toContain('tutorial');

    // Check that index page was generated
    const indexHtml = await readFile(
      join(outputDir, 'index.html'),
      'utf-8',
    );
    expect(indexHtml).toContain('Test Blog');

    // Check that tag page was generated
    const tagHtml = await readFile(
      join(outputDir, 'tags', 'javascript', 'index.html'),
      'utf-8',
    );
    expect(tagHtml).toContain('Tag: javascript');

    // Check RSS feed
    const rss = await readFile(join(outputDir, 'feed.xml'), 'utf-8');
    expect(rss).toContain('<rss version="2.0"');
    expect(rss).toContain('<title>Hello World</title>');
    expect(rss).toContain('https://test.example.com');

    // Check that code highlighting is applied
    expect(postHtml).toContain('hljs');
  });

  it('excludes draft posts by default', async () => {
    const outputDir = join(tmpDir, 'output-no-drafts');
    const sourceDir = join(FIXTURES, 'content');
    const templatesDir = join(FIXTURES, 'templates');

    await build({
      source: sourceDir,
      templates: templatesDir,
      output: outputDir,
    });

    // post-with-tags should exist (not a draft)
    const postHtml = await readFile(
      join(outputDir, 'post-with-tags', 'index.html'),
      'utf-8',
    );
    expect(postHtml).toContain('Hello World');

    // draft-post should not exist since drafts are excluded
    await expect(
      readFile(join(outputDir, 'draft-post', 'index.html'), 'utf-8'),
    ).rejects.toThrow();
  });

  it('includes draft posts when includeDrafts is true', async () => {
    const outputDir = join(tmpDir, 'output-with-drafts');
    const sourceDir = join(FIXTURES, 'content');
    const templatesDir = join(FIXTURES, 'templates');

    await build({
      source: sourceDir,
      templates: templatesDir,
      output: outputDir,
      includeDrafts: true,
    });

    const draftHtml = await readFile(
      join(outputDir, 'draft-post', 'index.html'),
      'utf-8',
    );
    expect(draftHtml).toContain('Draft Post');
  });

  it('handles posts with no frontmatter', async () => {
    const outputDir = join(tmpDir, 'output-no-fm');
    const sourceDir = join(FIXTURES, 'content');
    const templatesDir = join(FIXTURES, 'templates');

    await build({
      source: sourceDir,
      templates: templatesDir,
      output: outputDir,
    });

    const html = await readFile(
      join(outputDir, 'no-frontmatter', 'index.html'),
      'utf-8',
    );
    expect(html).toContain('no-frontmatter');
    expect(html).toContain('hljs');
  });

  it('respects site.json config', async () => {
    const outputDir = join(tmpDir, 'output-config');
    const sourceDir = join(FIXTURES, 'content');
    const templatesDir = join(FIXTURES, 'templates');

    await build({
      source: sourceDir,
      templates: templatesDir,
      output: outputDir,
    });

    const indexHtml = await readFile(
      join(outputDir, 'index.html'),
      'utf-8',
    );
    // site.json has title "Test Blog"
    expect(indexHtml).toContain('Test Blog');
    expect(indexHtml).toContain('A test blog for unit testing');
  });

  it('CLI options override site.json', async () => {
    const outputDir = join(tmpDir, 'output-override');
    const sourceDir = join(FIXTURES, 'content');
    const templatesDir = join(FIXTURES, 'templates');

    await build({
      source: sourceDir,
      templates: templatesDir,
      output: outputDir,
      title: 'Override Title',
      description: 'Override desc',
      url: 'https://override.example.com',
    });

    const indexHtml = await readFile(
      join(outputDir, 'index.html'),
      'utf-8',
    );
    expect(indexHtml).toContain('Override Title');

    const rss = await readFile(join(outputDir, 'feed.xml'), 'utf-8');
    expect(rss).toContain('https://override.example.com');
  });
});
