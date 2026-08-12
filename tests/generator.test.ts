import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, parseMarkdown } from '../src/generator';

describe('static site generator', () => {
  it('parses frontmatter and markdown', async () => {
    const page = await parseMarkdown('/tmp/hello-world.md', '---\ntitle: Hello\ndate: 2024-01-02\ntags: [news, intro]\n---\n\n## Welcome\n\n**world**');
    expect(page.frontmatter).toEqual({ title: 'Hello', date: '2024-01-02', tags: ['news', 'intro'] });
    expect(page.html).toContain('<h2>Welcome</h2>');
    expect(page.outputPath).toBe('hello-world.html');
  });

  it('builds an index and nested pages', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await fs.mkdir(path.join(content, 'notes'), { recursive: true });
    await fs.writeFile(path.join(content, 'about.md'), '---\ntitle: About\n---\nAbout us.');
    await fs.writeFile(path.join(content, 'notes', 'first.md'), '# First');
    await buildSite({ contentDir: content, outputDir: output });
    expect(await fs.readFile(path.join(output, 'about.html'), 'utf8')).toContain('<title>About</title>');
    expect(await fs.readFile(path.join(output, 'notes', 'first.html'), 'utf8')).toContain('<h1>First</h1>');
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');
    expect(index).toContain('href="about.html"');
    expect(index).toContain('href="notes/first.html"');
  });
});
