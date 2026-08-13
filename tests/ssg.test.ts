import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, parseMarkdown, renderPage } from '../src';
import { createProgram } from '../src/cli';

describe('static site generator', () => {
  let workspace: string;

  beforeEach(async () => {
    workspace = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
  });

  afterEach(async () => {
    await fs.rm(workspace, { recursive: true, force: true });
  });

  test('parses Markdown and normalizes frontmatter', () => {
    const page = parseMarkdown(`---\ntitle: Hello <World>\ndate: 2024-02-03\ntags: one, two\n---\n# Welcome\n\nThis is **bold**.`, 'hello.md');

    expect(page).toMatchObject({
      title: 'Hello <World>',
      date: '2024-02-03',
      tags: ['one', 'two'],
      outputPath: 'hello.html',
      url: 'hello.html',
    });
    expect(page.html).toContain('<strong>bold</strong>');
    expect(renderPage(page)).toContain('<title>Hello &lt;World&gt;</title>');
  });

  test('uses a readable filename when title is absent', () => {
    expect(parseMarkdown('# Post', 'my-first_post.md').title).toBe('My First Post');
  });

  test('keeps a root index page separate from the generated listing', () => {
    const page = parseMarkdown('# Home', 'index.md');

    expect(page.outputPath).toBe('index-page.html');
    expect(page.url).toBe('index-page.html');
  });

  test('builds nested pages and a date-sorted index', async () => {
    const content = path.join(workspace, 'content');
    const output = path.join(workspace, 'public');
    await fs.mkdir(path.join(content, 'notes'), { recursive: true });
    await fs.writeFile(path.join(content, 'older.md'), '---\ntitle: Older\ndate: 2023-01-01\n---\nOld');
    await fs.writeFile(path.join(content, 'notes', 'new.md'), '---\ntitle: Newer\ndate: 2024-01-01\ntags:\n  - news\n---\nNew');
    await fs.writeFile(path.join(content, 'ignore.txt'), 'not content');

    const pages = await buildSite({ contentDir: content, outputDir: output });
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');
    const nested = await fs.readFile(path.join(output, 'notes', 'new.html'), 'utf8');

    expect(pages.map((page) => page.title)).toEqual(['Newer', 'Older']);
    expect(index).toContain('href="notes/new.html"');
    expect(index.indexOf('Newer')).toBeLessThan(index.indexOf('Older'));
    expect(nested).toContain('<li>news</li>');
    await expect(fs.stat(path.join(output, 'ignore.html'))).rejects.toThrow();
  });

  test('cleans stale output and supports an empty content directory', async () => {
    const content = path.join(workspace, 'content');
    const output = path.join(workspace, 'output');
    await fs.mkdir(content);
    await fs.mkdir(output);
    await fs.writeFile(path.join(output, 'stale.html'), 'stale');

    await expect(buildSite({ contentDir: content, outputDir: output })).resolves.toEqual([]);
    await expect(fs.stat(path.join(output, 'stale.html'))).rejects.toThrow();
    await expect(fs.readFile(path.join(output, 'index.html'), 'utf8')).resolves.toContain('No pages found.');
  });

  test('reports a missing content directory', async () => {
    await expect(buildSite({
      contentDir: path.join(workspace, 'missing'),
      outputDir: path.join(workspace, 'output'),
    })).rejects.toThrow('Content directory does not exist');
  });

  test('refuses overlapping content and output directories', async () => {
    const content = path.join(workspace, 'content');
    await fs.mkdir(content);

    await expect(buildSite({
      contentDir: content,
      outputDir: path.join(content, 'dist'),
    })).rejects.toThrow('Content and output directories must not overlap');
    await expect(buildSite({
      contentDir: content,
      outputDir: workspace,
    })).rejects.toThrow('Content and output directories must not overlap');
  });

  test('CLI build honors content and output options', async () => {
    const content = path.join(workspace, 'articles');
    const output = path.join(workspace, 'site');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'page.md'), '# CLI page');
    const write = jest.spyOn(process.stdout, 'write').mockImplementation(() => true);

    await createProgram().parseAsync(['node', 'ssg', 'build', '--content', content, '--output', output]);

    await expect(fs.readFile(path.join(output, 'page.html'), 'utf8')).resolves.toContain('<h1>CLI page</h1>');
    expect(write).toHaveBeenCalledWith(`Generated 1 page in ${output}\n`);
    write.mockRestore();
  });
});
