import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from './generator';

describe('buildSite', () => {
  it('renders frontmatter Markdown pages and an index', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'site');
    await mkdir(join(content, 'guides'), { recursive: true });
    await writeFile(join(content, 'hello.md'), '---\ntitle: Hello World\ndate: 2026-08-13\ntags:\n  - welcome\n---\n# Hello\n\nA **site**.', 'utf8');
    await writeFile(join(content, 'guides', 'start.markdown'), '# Start here', 'utf8');

    const pages = await buildSite({ contentDir: content, outputDir: output });

    expect(pages).toEqual(expect.arrayContaining([
      expect.objectContaining({ title: 'Hello World', date: '2026-08-13', tags: ['welcome'], slug: 'hello.html' }),
      expect.objectContaining({ title: 'start', slug: 'guides/start.html' }),
    ]));
    await expect(readFile(join(output, 'hello.html'), 'utf8')).resolves.toContain('<h1>Hello</h1>');
    await expect(readFile(join(output, 'guides', 'start.html'), 'utf8')).resolves.toContain('<h1>Start here</h1>');
    await expect(readFile(join(output, 'index.html'), 'utf8')).resolves.toContain('<a href="hello.html">Hello World</a>');
  });

  it('rejects a missing content directory', async () => {
    await expect(buildSite({ contentDir: join(tmpdir(), 'missing-ssg-content') })).rejects.toThrow('Content directory does not exist');
  });
});
