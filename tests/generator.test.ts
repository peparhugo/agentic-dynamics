import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { buildSite, parseMarkdown } from '../src/generator';

describe('static site generator', () => {
  it('parses YAML frontmatter and markdown', () => {
    const page = parseMarkdown('---\ntitle: Hello World\ndate: 2024-01-02\ntags: [news, intro]\n---\n\n**Welcome**', 'hello.md');
    expect(page.title).toBe('Hello World');
    expect(page.date).toBe('2024-01-02');
    expect(page.tags).toEqual(['news', 'intro']);
    expect(page.html).toContain('<strong>Welcome</strong>');
  });

  it('builds an index and one HTML file per markdown page', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'first.md'), '---\ntitle: First\ndate: 2024-02-01\n---\nFirst page');
    await fs.writeFile(path.join(content, 'second.md'), '# Second');

    const pages = await buildSite(content, output);
    expect(pages.map((page) => page.title)).toEqual(['First', 'Second']);
    expect(await fs.readFile(path.join(output, 'first.html'), 'utf8')).toContain('<h1>First</h1>');
    expect(await fs.readFile(path.join(output, 'index.html'), 'utf8')).toContain('second.html');
  });
});
