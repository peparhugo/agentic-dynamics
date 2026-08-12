import { promises as fs } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import {
  collectPages,
  buildSite,
  renderIndex,
  renderPage
} from '../src/generator';

async function makeContent(dir: string, files: Record<string, string>): Promise<void> {
  await fs.mkdir(dir, { recursive: true });
  for (const [name, contents] of Object.entries(files)) {
    await fs.writeFile(join(dir, name), contents, 'utf8');
  }
}

describe('collectPages', () => {
  it('reads all markdown files and skips non-md files', async () => {
    const dir = join(tmpdir(), `ssg-collect-${Date.now()}`);
    await makeContent(dir, {
      'a.md': '---\ntitle: A\n---\n# A',
      'b.md': '---\ntitle: B\n---\n# B',
      'notes.txt': 'not markdown'
    });

    const pages = await collectPages(dir);
    expect(pages).toHaveLength(2);
    expect(pages.map((p) => p.slug).sort()).toEqual(['a', 'b']);
    await fs.rm(dir, { recursive: true, force: true });
  });

  it('returns an empty list for an empty directory', async () => {
    const dir = join(tmpdir(), `ssg-empty-${Date.now()}`);
    await fs.mkdir(dir, { recursive: true });
    const pages = await collectPages(dir);
    expect(pages).toEqual([]);
    await fs.rm(dir, { recursive: true, force: true });
  });
});

describe('buildSite', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(async () => {
    contentDir = join(tmpdir(), `ssg-content-${Date.now()}`);
    outputDir = join(tmpdir(), `ssg-dist-${Date.now()}`);
    await makeContent(contentDir, {
      'hello-world.md': [
        '---',
        'title: Hello World',
        'date: 2024-01-01',
        'tags: [intro, demo]',
        '---',
        '',
        '## Welcome',
        '',
        'This is **bold**.'
      ].join('\n'),
      'about.md': '---\ntitle: About\n---\n\n# About us'
    });
  });

  afterEach(async () => {
    await fs.rm(contentDir, { recursive: true, force: true });
    await fs.rm(outputDir, { recursive: true, force: true });
  });

  it('generates index.html and one HTML file per page', async () => {
    const pages = await buildSite({ contentDir, outputDir });

    expect(pages).toHaveLength(2);

    const index = await fs.readFile(join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('Hello World');
    expect(index).toContain('About');

    const hello = await fs.readFile(join(outputDir, 'hello-world.html'), 'utf8');
    expect(hello).toContain('Hello World');
    expect(hello).toContain('<strong>bold</strong>');
    expect(hello).toContain('<h2>Welcome</h2>');

    const about = await fs.readFile(join(outputDir, 'about.html'), 'utf8');
    expect(about).toContain('About us');

    const files = await fs.readdir(outputDir);
    expect(files).toEqual(expect.arrayContaining(['index.html', 'hello-world.html', 'about.html']));
  });

  it('creates the output directory when it does not exist', async () => {
    await fs.rm(outputDir, { recursive: true, force: true });
    await buildSite({ contentDir, outputDir });
    const stat = await fs.stat(outputDir);
    expect(stat.isDirectory()).toBe(true);
  });

  it('renders tags on the index page', async () => {
    await buildSite({ contentDir, outputDir });
    const index = await fs.readFile(join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('intro');
    expect(index).toContain('demo');
  });
});

describe('renderIndex', () => {
  it('includes an SPA runtime payload', () => {
    const html = renderIndex([]);
    expect(html).toContain('id="ssg-data"');
    expect(html).toContain('application/json');
  });
});

describe('renderPage', () => {
  it('renders a standalone HTML document', () => {
    const html = renderPage({
      slug: 'x',
      title: 'X',
      date: null,
      tags: ['t'],
      contentHtml: '<p>hi</p>',
      raw: '',
      frontmatter: {},
      fileName: 'x.md'
    });
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>X</title>');
    expect(html).toContain('<p>hi</p>');
  });
});
