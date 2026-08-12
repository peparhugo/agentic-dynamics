import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';

describe('buildSite', () => {
  it('renders frontmatter Markdown and an index', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await fs.mkdir(path.join(content, 'notes'), { recursive: true });
    await fs.writeFile(path.join(content, 'notes', 'hello.md'), '---\ntitle: Hello\ndate: 2026-01-02\ntags: [one, two]\n---\n\n**Welcome**');

    const pages = await buildSite({ contentDir: content, outputDir: output });
    const page = await fs.readFile(path.join(output, 'notes', 'hello.html'), 'utf8');
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');

    expect(pages[0]).toMatchObject({ title: 'Hello', date: '2026-01-02', tags: ['one', 'two'] });
    expect(page).toContain('<strong>Welcome</strong>');
    expect(page).toContain('<title>Hello</title>');
    expect(index).toContain('href="notes/hello.html"');
  });
});
