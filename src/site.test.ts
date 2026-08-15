import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite, parsePage } from './site';

describe('parsePage', () => {
  it('parses simple YAML frontmatter and renders Markdown', () => {
    const page = parsePage('---\ntitle: Hello World\ndate: 2026-08-15\ntags: [typescript, static]\n---\n\n# Welcome', 'hello-world.md');

    expect(page).toMatchObject({ title: 'Hello World', date: '2026-08-15', tags: ['typescript', 'static'], slug: 'hello-world' });
    expect(page.html).toContain('<h1>Welcome</h1>');
  });

  it('uses the filename as a title when frontmatter has no title', () => {
    expect(parsePage('A page', 'my-page.md').title).toBe('my page');
  });
});

describe('buildSite', () => {
  it('creates a page HTML file and an index', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'output');
    await mkdir(content);
    await writeFile(join(content, 'first-post.md'), '---\ntitle: First Post\ntags: news, updates\n---\n\nBody');

    await buildSite({ contentDir: content, outputDir: output });

    await expect(readFile(join(output, 'first-post.html'), 'utf8')).resolves.toContain('<h1>First Post</h1>');
    await expect(readFile(join(output, 'index.html'), 'utf8')).resolves.toContain('href="first-post.html"');
  });
});
