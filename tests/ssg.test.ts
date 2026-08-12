import { promises as fs } from 'fs';
import * as os from 'os';
import * as path from 'path';

import {
  build,
  escapeHtml,
  listMarkdownFiles,
  pagePath,
  parseMarkdownFile,
  renderIndex,
  renderPage,
} from '../src/ssg';
import { parseArgs, printHelp } from '../src/cli';
import type { Page } from '../src/types';

const FIXTURES = path.join(__dirname, 'fixtures');
const CONTENT_DIR = path.join(FIXTURES, 'content');

let tempRoot: string;
let outputDir: string;

beforeAll(async () => {
  tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-test-'));
  outputDir = path.join(tempRoot, 'dist');
});

afterAll(async () => {
  await fs.rm(tempRoot, { recursive: true, force: true });
});

describe('listMarkdownFiles', () => {
  it('recursively finds markdown files sorted by path', async () => {
    const files = await listMarkdownFiles(CONTENT_DIR);
    const relative = files.map((file) => path.relative(CONTENT_DIR, file).replace(/\\/g, '/'));
    expect(relative).toEqual(['fixture-one.md', 'sub/fixture-two.md']);
  });
});

describe('parseMarkdownFile', () => {
  it('parses frontmatter fields and renders markdown to HTML', async () => {
    const page = await parseMarkdownFile(path.join(CONTENT_DIR, 'fixture-one.md'));
    expect(page.slug).toBe('fixture-one');
    expect(page.title).toBe('Fixture One');
    expect(page.date).toBe('2023-06-01');
    expect(page.tags).toEqual(['alpha', 'beta']);
    expect(page.html).toContain('<h1>Fixture One</h1>');
    expect(page.html).toContain('<strong>fixture</strong>');
  });

  it('parses tags given as a comma-separated string', async () => {
    const page = await parseMarkdownFile(path.join(CONTENT_DIR, 'sub', 'fixture-two.md'));
    expect(page.tags).toEqual(['gamma', 'delta']);
    expect(page.html).toContain('<a href="https://example.com">link</a>');
  });

  it('falls back to the filename for the title when frontmatter is missing', async () => {
    const page = await parseMarkdownFile(path.join(FIXTURES, 'raw.md'));
    expect(page.slug).toBe('raw');
    expect(page.title).toBe('Raw Title');
  });
});

describe('renderPage', () => {
  const page: Page = {
    slug: 'demo',
    title: 'Demo <Page>',
    date: '2024-03-04',
    tags: ['one', 'two'],
    content: 'Body',
    html: '<p>Body</p>',
  };

  it('produces a full HTML document with the title, date, and tags', () => {
    const html = renderPage(page);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Demo &lt;Page&gt;</title>');
    expect(html).toContain('<h1>Demo &lt;Page&gt;</h1>');
    expect(html).toContain('datetime="2024-03-04"');
    expect(html).toContain('<p>Body</p>');
    expect(html).toContain('<span class="tag">one</span>');
    expect(html).toContain('<a href="index.html">Home</a>');
  });
});

describe('renderIndex', () => {
  it('lists pages sorted by date descending with links', () => {
    const pages: Page[] = [
      {
        slug: 'a',
        title: 'A',
        date: '2024-01-01',
        tags: [],
        content: '',
        html: '',
      },
      {
        slug: 'b',
        title: 'B',
        date: '2025-01-01',
        tags: ['x'],
        content: '',
        html: '',
      },
      {
        slug: 'c',
        title: 'C',
        date: undefined,
        tags: [],
        content: '',
        html: '',
      },
    ];
    const html = renderIndex(pages);
    expect(html).toContain('<a href="a.html">A</a>');
    expect(html).toContain('<a href="b.html">B</a>');
    expect(html).toContain('<a href="c.html">C</a>');
    const indexB = html.indexOf('>B</a>');
    const indexA = html.indexOf('>A</a>');
    const indexC = html.indexOf('>C</a>');
    expect(indexB).toBeGreaterThan(-1);
    expect(indexB).toBeLessThan(indexA);
    expect(indexA).toBeLessThan(indexC);
    expect(html).toContain('x');
  });
});

describe('build', () => {
  it('writes index.html and one HTML file per page to the output directory', async () => {
    const pages = await build({
      contentDir: CONTENT_DIR,
      outputDir,
      templateDir: path.join(FIXTURES, 'does-not-exist'),
    });
    expect(pages).toHaveLength(2);

    const files = (await fs.readdir(outputDir)).sort();
    expect(files).toEqual(['fixture-one.html', 'fixture-two.html', 'index.html']);

    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('Fixture One');
    expect(index).toContain('Fixture Two');
    expect(index).toContain('fixture-one.html');

    const pageHtml = await fs.readFile(path.join(outputDir, 'fixture-two.html'), 'utf8');
    expect(pageHtml).toContain('<h1>Fixture Two</h1>');
    expect(pageHtml).toContain('<a href="https://example.com">link</a>');
  });
});

describe('parseArgs', () => {
  it('uses defaults for build', () => {
    expect(parseArgs(['build'])).toEqual({
      contentDir: 'content',
      outputDir: 'dist',
      templateDir: 'templates',
    });
  });

  it('honors --content and --output', () => {
    expect(parseArgs(['build', '--content', 'src/posts', '--output', 'public'])).toEqual({
      contentDir: 'src/posts',
      outputDir: 'public',
      templateDir: 'templates',
    });
  });

  it('honors --templates', () => {
    expect(parseArgs(['build', '--templates', 'theme'])).toEqual({
      contentDir: 'content',
      outputDir: 'dist',
      templateDir: 'theme',
    });
  });

  it('returns help for --help', () => {
    expect(parseArgs(['--help'])).toBe('help');
    expect(parseArgs(['build', '-h'])).toBe('help');
  });

  it('returns invalid for unknown subcommands or missing option values', () => {
    expect(parseArgs([])).toBe('invalid');
    expect(parseArgs(['frobnicate'])).toBe('invalid');
    expect(parseArgs(['build', '--content'])).toBe('invalid');
    expect(parseArgs(['build', '--templates'])).toBe('invalid');
    expect(parseArgs(['build', '--output', '--content', 'x'])).toBe('invalid');
  });
});

describe('utilities', () => {
  it('slugifies filenames with spaces, caps, and extensions', async () => {
    const file = path.join(FIXTURES, 'My Cool Post.md');
    await fs.writeFile(file, '# Hi\n');
    const page = await parseMarkdownFile(file);
    expect(page.slug).toBe('my-cool-post');
    expect(pagePath(page)).toBe('my-cool-post.html');
    await fs.unlink(file);
  });

  it('escapes HTML in titles and tag output', () => {
    expect(escapeHtml('<a href="x">&')).toBe('&lt;a href=&quot;x&quot;&gt;&amp;');
  });

  it('printHelp prints usage text', () => {
    const spy = jest.spyOn(console, 'log').mockImplementation(() => undefined);
    printHelp();
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('ssg build'));
    spy.mockRestore();
  });
});
