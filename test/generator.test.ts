import { mkdtemp, readFile, rm, writeFile, mkdir } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { buildSite, readPages } from '../src/generator';

describe('static site generator', () => {
  let directory: string;
  let content: string;
  let output: string;

  beforeEach(async () => {
    directory = await mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    content = path.join(directory, 'content');
    output = path.join(directory, 'site');
    await mkdir(content);
  });

  afterEach(async () => rm(directory, { recursive: true, force: true }));

  it('parses frontmatter and Markdown', async () => {
    await writeFile(path.join(content, 'hello.md'), '---\ntitle: Hello World\ndate: 2025-01-02\ntags:\n  - news\n---\n# Welcome\n\n**Text**');

    const pages = await readPages(content);

    expect(pages).toEqual([expect.objectContaining({ slug: 'hello', title: 'Hello World', date: '2025-01-02', tags: ['news'], html: expect.stringContaining('<h1>Welcome</h1>') })]);
  });

  it('writes a page and an index to the requested output directory', async () => {
    await writeFile(path.join(content, 'first.md'), '---\ntitle: First Post\n---\nA post.');
    await writeFile(path.join(content, 'second.md'), '# Second');

    await buildSite({ contentDir: content, outputDir: output });

    await expect(readFile(path.join(output, 'first.html'), 'utf8')).resolves.toContain('<title>First Post</title>');
    await expect(readFile(path.join(output, 'second.html'), 'utf8')).resolves.toContain('<h1>Second</h1>');
    await expect(readFile(path.join(output, 'index.html'), 'utf8')).resolves.toContain('<a href="first.html">First Post</a>');
  });
});
