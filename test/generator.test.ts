import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';

describe('buildSite', () => {
  test('builds Markdown pages and an index from frontmatter', async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await mkdir(path.join(content, 'notes'), { recursive: true });
    await writeFile(path.join(content, 'welcome.md'), '---\ntitle: Welcome\ndate: 2026-01-01\ntags: [intro, news]\n---\n\n# Hello\n\nThis is **Markdown**.');
    await writeFile(path.join(content, 'notes', 'second.md'), '# Second');

    const pages = await buildSite({ contentDir: content, outputDir: output });

    expect(pages).toHaveLength(2);
    expect(await readFile(path.join(output, 'welcome.html'), 'utf8')).toContain('<h1>Welcome</h1>');
    expect(await readFile(path.join(output, 'welcome.html'), 'utf8')).toContain('<strong>Markdown</strong>');
    expect(await readFile(path.join(output, 'notes', 'second.html'), 'utf8')).toContain('<h1>Second</h1>');
    expect(await readFile(path.join(output, 'index.html'), 'utf8')).toContain('href="/welcome.html"');
    expect(await readFile(path.join(output, 'index.html'), 'utf8')).toContain('href="/notes/second.html"');
  });

  test('removes stale generated files', async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await mkdir(content, { recursive: true });
    await mkdir(output, { recursive: true });
    await writeFile(path.join(output, 'old.html'), 'old');
    await writeFile(path.join(content, 'page.md'), '---\ntitle: Page\n---\nContent');

    await buildSite({ contentDir: content, outputDir: output });

    await expect(readFile(path.join(output, 'old.html'))).rejects.toMatchObject({ code: 'ENOENT' });
  });
});
