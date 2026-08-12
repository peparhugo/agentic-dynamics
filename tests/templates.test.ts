import { promises as fs } from 'fs';
import * as os from 'os';
import * as path from 'path';

import {
  loadTemplateEngine,
  renderIndexWithTemplates,
  renderPageWithTemplates,
  type FallbackRenderers,
  type TemplateEngine,
} from '../src/templates';
import { build, parseMarkdownFile, renderDocument } from '../src/ssg';
import type { Page } from '../src/types';

const FIXTURES = path.join(__dirname, 'fixtures');
const TEMPLATES = path.join(FIXTURES, 'templates');
const TEMPLATE_CONTENT = path.join(FIXTURES, 'template-content');
const NO_LAYOUT_TEMPLATES = path.join(FIXTURES, 'templates-no-layout');

let tempRoot: string;
let outputDir: string;

beforeAll(async () => {
  tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-templates-test-'));
  outputDir = path.join(tempRoot, 'dist');
});

afterAll(async () => {
  await fs.rm(tempRoot, { recursive: true, force: true });
});

describe('parseMarkdownFile template frontmatter', () => {
  it('parses template and layout fields from frontmatter', async () => {
    const page = await parseMarkdownFile(path.join(TEMPLATE_CONTENT, 'posts', 'hello.md'));
    expect(page.template).toBe('post');
    expect(page.layout).toBe('default');
    expect(page.data).toMatchObject({ title: 'Hello Post' });
  });

  it('leaves template and layout undefined when absent', async () => {
    const page = await parseMarkdownFile(path.join(TEMPLATE_CONTENT, 'plain.md'));
    expect(page.template).toBeUndefined();
    expect(page.layout).toBeUndefined();
  });
});

describe('loadTemplateEngine', () => {
  it('returns null when the template directory does not exist', async () => {
    const engine = await loadTemplateEngine(path.join(FIXTURES, 'does-not-exist'));
    expect(engine).toBeNull();
  });

  it('loads page templates, layouts, and registers partials', async () => {
    const engine = await loadTemplateEngine(TEMPLATES);
    expect(engine).not.toBeNull();
    expect(engine!.pageTemplates.has('default')).toBe(true);
    expect(engine!.pageTemplates.has('post')).toBe(true);
    expect(engine!.layouts.has('default')).toBe(true);
    expect(engine!.layouts.has('wide')).toBe(true);
  });
});

describe('renderPageWithTemplates', () => {
  let engine: TemplateEngine;
  const fallbacks: FallbackRenderers = {
    document: renderDocument,
    indexBody: () => '<ul></ul>',
    indexDocument: () => '<html></html>',
  };

  beforeAll(async () => {
    engine = (await loadTemplateEngine(TEMPLATES))!;
  });

  it('uses the default template and default layout when none specified', async () => {
    const page = await parseMarkdownFile(path.join(TEMPLATE_CONTENT, 'plain.md'));
    const html = renderPageWithTemplates(page, engine, fallbacks);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<article>');
    expect(html).toContain('<h1>Plain Page</h1>');
    expect(html).toContain('<p>A plain page.</p>');
    expect(html).toContain('class="site-header"');
    expect(html).toContain('class="site-footer"');
  });

  it('uses the template named in frontmatter', async () => {
    const page = await parseMarkdownFile(path.join(TEMPLATE_CONTENT, 'posts', 'hello.md'));
    const html = renderPageWithTemplates(page, engine, fallbacks);
    expect(html).toContain('<article class="post">');
    expect(html).toContain('<h1>Hello Post</h1>');
    expect(html).toContain('<time datetime="2024-01-15">2024-01-15</time>');
    expect(html).toContain('<strong>post</strong>');
  });

  it('uses the layout named in frontmatter', async () => {
    const page = await parseMarkdownFile(path.join(TEMPLATE_CONTENT, 'about.md'));
    const html = renderPageWithTemplates(page, engine, fallbacks);
    expect(html).toContain('<body class="wide">');
    expect(html).toContain('class="nav"');
    expect(html).toContain('<h1>About</h1>');
  });

  it('renders partials inside layouts via the body placeholder', async () => {
    const page = await parseMarkdownFile(path.join(TEMPLATE_CONTENT, 'posts', 'hello.md'));
    const html = renderPageWithTemplates(page, engine, fallbacks);
    const bodyStart = html.indexOf('<main>');
    const bodyEnd = html.indexOf('</main>');
    expect(bodyStart).toBeGreaterThan(-1);
    expect(bodyEnd).toBeGreaterThan(bodyStart);
    const main = html.slice(bodyStart, bodyEnd);
    expect(main).toContain('<article class="post">');
    expect(main).not.toContain('site-footer');
  });

  it('escapes template variable output but not triple-stash HTML', async () => {
    const page: Page = {
      slug: 'x',
      title: 'Danger <b>',
      tags: [],
      content: '',
      html: '<p>raw</p>',
    };
    const html = renderPageWithTemplates(page, engine, fallbacks);
    expect(html).toContain('<h1>Danger &lt;b&gt;</h1>');
    expect(html).toContain('<p>raw</p>');
  });

  it('throws when an explicit template is missing', async () => {
    const brokenFile = path.join(tempRoot, 'broken.md');
    await fs.writeFile(brokenFile, '---\ntitle: Broken\ntemplate: nope\n---\n\nOops.\n');
    const page = await parseMarkdownFile(brokenFile);
    expect(() => renderPageWithTemplates(page, engine, fallbacks)).toThrow(
      'Template not found: nope'
    );
  });

  it('throws when an explicit layout is missing', async () => {
    const page: Page = {
      slug: 'x',
      title: 'X',
      tags: [],
      content: '',
      html: '',
      layout: 'missing',
    };
    expect(() => renderPageWithTemplates(page, engine, fallbacks)).toThrow(
      'Layout not found: missing'
    );
  });

  it('falls back to the legacy document when no layouts are configured', async () => {
    const noLayoutEngine = (await loadTemplateEngine(NO_LAYOUT_TEMPLATES))!;
    const page = await parseMarkdownFile(path.join(TEMPLATE_CONTENT, 'plain.md'));
    const html = renderPageWithTemplates(page, noLayoutEngine, fallbacks);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<article>');
    expect(html).toContain('<h1>Plain Page</h1>');
    expect(html).not.toContain('site-header');
  });
});

describe('renderIndexWithTemplates', () => {
  const pages: Page[] = [
    {
      slug: 'a',
      title: 'Alpha',
      date: '2024-01-01',
      tags: [],
      content: '',
      html: '',
    },
    {
      slug: 'b',
      title: 'Beta',
      date: '2025-01-01',
      tags: [],
      content: '',
      html: '',
    },
  ];

  it('renders the index template inside the default layout', async () => {
    const engine = (await loadTemplateEngine(TEMPLATES))!;
    const html = renderIndexWithTemplates(pages, engine, {
      document: renderDocument,
      indexBody: () => '<ul></ul>',
      indexDocument: () => '<html></html>',
    });
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<ul class="post-list">');
    expect(html).toContain('<a href="a.html">Alpha</a>');
    expect(html).toContain('<a href="b.html">Beta</a>');
    expect(html).toContain('class="site-header"');
  });

  it('falls back to the legacy index document when no index template or layout exists', async () => {
    const noLayoutEngine = (await loadTemplateEngine(NO_LAYOUT_TEMPLATES))!;
    const html = renderIndexWithTemplates(pages, noLayoutEngine, {
      document: renderDocument,
      indexBody: () => '<ul></ul>',
      indexDocument: (list) => `LEGACY(${list.length})`,
    });
    expect(html).toBe('LEGACY(2)');
  });
});

describe('build with templates', () => {
  it('renders every page and the index through templates', async () => {
    const pages = await build({ contentDir: TEMPLATE_CONTENT, outputDir, templateDir: TEMPLATES });
    expect(pages.map((page) => page.slug).sort()).toEqual(['about', 'hello', 'plain']);

    const files = (await fs.readdir(outputDir)).sort();
    expect(files).toEqual(['about.html', 'hello.html', 'index.html', 'plain.html']);

    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('<ul class="post-list">');
    expect(index).toContain('<a href="hello.html">Hello Post</a>');

    const hello = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    expect(hello).toContain('<article class="post">');
    expect(hello).toContain('<h1>Hello Post</h1>');
    expect(hello).toContain('class="site-header"');

    const about = await fs.readFile(path.join(outputDir, 'about.html'), 'utf8');
    expect(about).toContain('<body class="wide">');

    const plain = await fs.readFile(path.join(outputDir, 'plain.html'), 'utf8');
    expect(plain).toContain('<article>');
    expect(plain).toContain('<h1>Plain Page</h1>');
  });
});
