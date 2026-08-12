import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';

describe('buildSite', () => {
  let root: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    await fs.mkdir(path.join(root, 'content', 'notes'), { recursive: true });
    await fs.writeFile(
      path.join(root, 'content', 'welcome.md'),
      ['---', 'title: Welcome', 'date: 2025-01-02', 'tags:', '  - intro', '  - ssg', '---', '# Hello', '', 'This is **Markdown**.'].join('\n'),
    );
    await fs.writeFile(path.join(root, 'content', 'notes', 'second.markdown'), '---\ntitle: Second\n---\nA second page.');
  });

  it('converts Markdown and frontmatter into page documents', async () => {
    const pages = await buildSite({ contentDir: path.join(root, 'content'), outputDir: path.join(root, 'dist') });
    const output = await fs.readFile(path.join(root, 'dist', 'welcome.html'), 'utf8');
    expect(pages).toHaveLength(2);
    expect(output).toContain('<title>Welcome</title>');
    expect(output).toContain('<h1>Hello</h1>');
    expect(output).toContain('<li>intro</li>');
    expect(output).toContain('2025-01-02');
  });

  it('creates an index and preserves nested output paths', async () => {
    await buildSite({ contentDir: path.join(root, 'content'), outputDir: path.join(root, 'dist') });
    const index = await fs.readFile(path.join(root, 'dist', 'index.html'), 'utf8');
    expect(index).toContain('welcome.html');
    expect(index).toContain('notes/second.html');
    await expect(fs.access(path.join(root, 'dist', 'notes', 'second.html'))).resolves.toBeUndefined();
  });

  it('uses the filename when a title is not provided', async () => {
    await fs.writeFile(path.join(root, 'content', 'untitled.md'), 'Plain text');
    await buildSite({ contentDir: path.join(root, 'content'), outputDir: path.join(root, 'dist') });
    const output = await fs.readFile(path.join(root, 'dist', 'untitled.html'), 'utf8');
    expect(output).toContain('<title>untitled</title>');
  });
});
