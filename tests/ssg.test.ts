import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, parseMarkdown } from '../src';

describe('static site generator', () => {
  it('parses frontmatter and Markdown', async () => {
    const page = await parseMarkdown('---\ntitle: Hello\ndate: 2024-01-01\ntags: [news, intro]\n---\n\n**Welcome**', 'hello.md');
    expect(page.title).toBe('Hello');
    expect(page.date).toBe('2024-01-01');
    expect(page.tags).toEqual(['news', 'intro']);
    expect(page.html).toContain('<strong>Welcome</strong>');
  });

  it('builds pages and an index, including nested Markdown files', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    await fs.mkdir(path.join(content, 'guide'), { recursive: true });
    await fs.writeFile(path.join(content, 'home.md'), '# Home');
    await fs.writeFile(path.join(content, 'guide', 'start.md'), '---\ntitle: Start\n---\nBegin');
    const pages = await buildSite({ contentDir: content, outputDir: output });
    expect(pages).toHaveLength(2);
    expect(await fs.readFile(path.join(output, 'index.html'), 'utf8')).toContain('guide/start.html');
    expect(await fs.readFile(path.join(output, 'guide', 'start.html'), 'utf8')).toContain('<h1>Start</h1>');
  });
});
