import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { escapeHtml, renderIndexHtml, renderPageHtml } from './templates';
import { Page } from './types';

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'hello',
    frontmatter: { title: 'Hello', date: '2026-01-01', tags: ['a', 'b'] },
    contentHtml: '<p>Body</p>',
    sourcePath: '/content/hello.md',
    ...overrides,
  };
}

describe('escapeHtml', () => {
  it('escapes special characters', () => {
    expect(escapeHtml('<script>alert("x")</script>')).toBe(
      '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;'
    );
  });
});

describe('renderPageHtml', () => {
  it('includes the title, meta, and content', () => {
    const html = renderPageHtml(makePage());
    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('<p>Body</p>');
    expect(html).toContain('2026-01-01');
    expect(html).toContain('a');
    expect(html).toContain('b');
  });

  it('escapes an untrusted title', () => {
    const page = makePage({ frontmatter: { title: '<img src=x>', date: undefined, tags: [] } });
    const html = renderPageHtml(page);
    expect(html).not.toContain('<img src=x>');
    expect(html).toContain('&lt;img src=x&gt;');
  });

  it('links back to a nested index correctly', () => {
    const page = makePage({ slug: 'posts/hello' });
    const html = renderPageHtml(page);
    expect(html).toContain('href="../index.html"');
  });
});

describe('renderIndexHtml', () => {
  it('lists every page with a link to its file', () => {
    const pages = [makePage({ slug: 'a', frontmatter: { title: 'A', tags: [] } }), makePage({ slug: 'b', frontmatter: { title: 'B', tags: [] } })];
    const html = renderIndexHtml(pages, 'My Site');
    expect(html).toContain('<title>My Site</title>');
    expect(html).toContain('href="a.html"');
    expect(html).toContain('href="b.html"');
    expect(html).toContain('>A<');
    expect(html).toContain('>B<');
  });
});

describe('template and layout selection', () => {
  let templatesDir: string;

  function writeFile(filePath: string, content: string): void {
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, content, 'utf-8');
  }

  beforeEach(() => {
    templatesDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-templates-'));
    writeFile(path.join(templatesDir, 'page.hbs'), '<article data-template="page">{{{content}}}</article>');
    writeFile(path.join(templatesDir, 'post.hbs'), '<article data-template="post">{{{content}}}</article>');
    writeFile(path.join(templatesDir, 'index.hbs'), '<ul>{{#each pages}}<li>{{{title}}}</li>{{/each}}</ul>');
    writeFile(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html data-layout="default"><body>{{> header}}{{{body}}}{{> footer}}</body></html>'
    );
    writeFile(
      path.join(templatesDir, 'layouts', 'wide.hbs'),
      '<html data-layout="wide"><body>{{> header}}{{{body}}}{{> footer}}</body></html>'
    );
    writeFile(path.join(templatesDir, 'partials', 'header.hbs'), '<header>{{{siteTitle}}}</header>');
    writeFile(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>&copy; {{{siteTitle}}}</footer>');
  });

  afterEach(() => {
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('uses the "page" template and "default" layout when a page specifies none', () => {
    const html = renderPageHtml(makePage(), { templatesDir });
    expect(html).toContain('data-template="page"');
    expect(html).toContain('data-layout="default"');
  });

  it('uses the template named in a page\'s frontmatter', () => {
    const page = makePage({ frontmatter: { title: 'Hello', date: undefined, tags: [], template: 'post' } });
    const html = renderPageHtml(page, { templatesDir });
    expect(html).toContain('data-template="post"');
  });

  it('uses the layout named in a page\'s frontmatter', () => {
    const page = makePage({ frontmatter: { title: 'Hello', date: undefined, tags: [], layout: 'wide' } });
    const html = renderPageHtml(page, { templatesDir });
    expect(html).toContain('data-layout="wide"');
  });

  it('renders header and footer partials into the page via the layout', () => {
    const html = renderPageHtml(makePage(), { templatesDir, siteTitle: 'Partial Site' });
    expect(html).toContain('<header>Partial Site</header>');
    expect(html).toContain('<footer>&copy; Partial Site</footer>');
  });

  it('renders the index page through the "index" template and partials', () => {
    const pages = [makePage({ slug: 'a', frontmatter: { title: 'A', tags: [] } })];
    const html = renderIndexHtml(pages, 'My Site', { templatesDir });
    expect(html).toContain('<li>A</li>');
    expect(html).toContain('<header>My Site</header>');
  });

  it('throws a clear error when a page requests a template that does not exist', () => {
    const page = makePage({ frontmatter: { title: 'Hello', date: undefined, tags: [], template: 'missing' } });
    expect(() => renderPageHtml(page, { templatesDir })).toThrow(/Template not found/);
  });
});
