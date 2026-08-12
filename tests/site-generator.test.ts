import fs from 'fs/promises';
import os from 'os';
import path from 'path';
import { buildSite, parseMarkdown } from '../src/site-generator';

async function temporaryDirectory(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-test-'));
}

describe('parseMarkdown', () => {
  test('parses frontmatter and Markdown content', () => {
    const page = parseMarkdown(
      '---\ntitle: Hello World\ndate: 2024-01-02\ntags:\n  - typescript\n  - web\n---\n\n## Heading\n\n**content**',
      'hello.md',
    );

    expect(page.title).toBe('Hello World');
    expect(page.date).toBe('2024-01-02');
    expect(page.tags).toEqual(['typescript', 'web']);
    expect(page.outputPath).toBe('hello.html');
    expect(page.html).toContain('<h2>Heading</h2>');
    expect(page.html).toContain('<strong>content</strong>');
  });

  test('uses the filename when title is absent and accepts comma-separated tags', () => {
    const page = parseMarkdown('---\ntags: typescript, web\n---\n\nBody', 'notes.md');
    expect(page.title).toBe('notes');
    expect(page.tags).toEqual(['typescript', 'web']);
    expect(page.html).toContain('<p>Body</p>');
  });
});

describe('buildSite', () => {
  test('writes pages and an index, including nested Markdown files', async () => {
    const root = await temporaryDirectory();
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    await fs.mkdir(path.join(content, 'guides'), { recursive: true });
    await fs.writeFile(path.join(content, 'first.md'), '---\ntitle: First\n---\nWelcome.');
    await fs.writeFile(path.join(content, 'guides', 'second.md'), '# Second');
    await fs.writeFile(path.join(content, 'skip.txt'), 'not Markdown');

    const result = await buildSite({ contentDir: content, outputDir: output });
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');
    const first = await fs.readFile(path.join(output, 'first.html'), 'utf8');
    const second = await fs.readFile(path.join(output, 'guides', 'second.html'), 'utf8');

    expect(result.pages).toHaveLength(2);
    expect(index).toContain('href="first.html"');
    expect(index).toContain('href="guides/second.html"');
    expect(index).toContain('First');
    expect(first).toContain('<h1>First</h1>');
    expect(first).toContain('<p>Welcome.</p>');
    expect(second).toContain('<h1>second</h1>');
    expect(second).toContain('<h1 id="second">Second</h1>');
  });

  test('creates an empty index for an empty content directory', async () => {
    const root = await temporaryDirectory();
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    await fs.mkdir(content);

    const result = await buildSite({ contentDir: content, outputDir: output });
    expect(result.pages).toEqual([]);
    expect(await fs.readFile(path.join(output, 'index.html'), 'utf8')).toContain('<ul>');
  });
});
