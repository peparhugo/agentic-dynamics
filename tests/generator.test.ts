import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from '../src/generator.js';

describe('buildSite', () => {
  it('renders frontmatter, markdown pages, and an index', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'site');
    await mkdir(content);
    await writeFile(join(content, 'hello.md'), '---\ntitle: Hello <World>\ndate: 2026-08-13\ntags:\n  - news\n  - typescript\n---\n\n# Welcome\n\nThis is **strong**.');

    const pages = await buildSite({ contentDir: content, outputDir: output });
    const page = await readFile(join(output, 'hello.html'), 'utf8');
    const index = await readFile(join(output, 'index.html'), 'utf8');

    expect(pages).toHaveLength(1);
    expect(page).toContain('<title>Hello &lt;World&gt;</title>');
    expect(page).toContain('<h1>Welcome</h1>');
    expect(page).toContain('<strong>strong</strong>');
    expect(page).not.toContain('---');
    expect(page).toContain('Tags: news, typescript');
    expect(index).toContain('href="hello.html"');
    expect(index).toContain('Hello &lt;World&gt;');
  });
});
