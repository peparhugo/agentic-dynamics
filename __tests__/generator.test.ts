import { promises as fs } from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build } from '../src/generator';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-test-'));
}

describe('build', () => {
  it('generates an HTML file for each page and an index', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir, { recursive: true });

    await fs.writeFile(
      path.join(contentDir, 'hello.md'),
      '---\ntitle: Hello\ndate: 2024-01-01\ntags: a, b\n---\n# Hello\nWorld',
      'utf8'
    );
    await fs.writeFile(
      path.join(contentDir, 'second.md'),
      '# Second',
      'utf8'
    );

    const pages = await build({ contentDir, outputDir });

    expect(pages).toHaveLength(2);

    const helloHtml = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    expect(helloHtml).toContain('<h1>Hello</h1>');
    expect(helloHtml).toContain('World');
    expect(helloHtml).toContain('2024-01-01');

    const secondHtml = await fs.readFile(path.join(outputDir, 'second.html'), 'utf8');
    expect(secondHtml).toContain('<h1>Second</h1>');

    const indexHtml = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');
    expect(indexHtml).toContain('href="hello.html"');
    expect(indexHtml).toContain('href="second.html"');
    expect(indexHtml).toContain('<h1>Index</h1>');
  });

  it('recursively discovers markdown in subdirectories', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(path.join(contentDir, 'nested', 'deeper'), { recursive: true });

    await fs.writeFile(
      path.join(contentDir, 'nested', 'deeper', 'doc.md'),
      '# Deep',
      'utf8'
    );

    const pages = await build({ contentDir, outputDir });
    expect(pages).toHaveLength(1);
    expect(pages[0].slug).toBe('nested-deeper-doc');

    const html = await fs.readFile(path.join(outputDir, 'nested-deeper-doc.html'), 'utf8');
    expect(html).toContain('<h1>Deep</h1>');
  });

  it('ignores non-markdown files', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir, { recursive: true });

    await fs.writeFile(path.join(contentDir, 'notes.txt'), 'not markdown', 'utf8');
    await fs.writeFile(path.join(contentDir, 'page.md'), '# Page', 'utf8');

    const pages = await build({ contentDir, outputDir });
    expect(pages).toHaveLength(1);
    expect(pages[0].slug).toBe('page');
  });

  it('throws when the content directory does not exist', async () => {
    const root = await makeTempDir();
    await expect(
      build({ contentDir: path.join(root, 'missing'), outputDir: path.join(root, 'dist') })
    ).rejects.toThrow('content directory not found');
  });

  it('creates an empty index for an empty content directory', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir, { recursive: true });

    const pages = await build({ contentDir, outputDir });
    expect(pages).toHaveLength(0);

    const indexHtml = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');
    expect(indexHtml).toContain('<h1>Index</h1>');
  });
});
