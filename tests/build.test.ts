import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import { buildSite, listMarkdownFiles } from '../src/build';
import { createFixture, cleanupFixture, Fixture } from './helpers';

describe('buildSite', () => {
  let fixture: Fixture;

  afterEach(() => {
    cleanupFixture(fixture);
  });

  it('generates an HTML file for every markdown page', () => {
    fixture = createFixture({
      'about.md': '---\ntitle: About\ntags: meta\n---\n\n## About us',
      'post.md': '---\ntitle: First Post\ndate: 2024-01-01\n---\n\nHello **world**.',
    });

    const pages = buildSite(fixture.contentDir, fixture.outputDir);

    expect(pages).toHaveLength(2);
    expect(existsSync(join(fixture.outputDir, 'about.html'))).toBe(true);
    expect(existsSync(join(fixture.outputDir, 'post.html'))).toBe(true);
  });

  it('renders markdown content into each page HTML', () => {
    fixture = createFixture({
      'post.md': '---\ntitle: First Post\ntags: [a, b]\n---\n\nHello **world**.',
    });

    buildSite(fixture.contentDir, fixture.outputDir);

    const pageHtml = readFileSync(join(fixture.outputDir, 'post.html'), 'utf8');
    expect(pageHtml).toContain('<title>First Post</title>');
    expect(pageHtml).toContain('<strong>world</strong>');
    expect(pageHtml).toContain('class="tag">a</span>');
  });

  it('generates an index.html listing all pages', () => {
    fixture = createFixture({
      'one.md': '---\ntitle: One\ndate: 2024-01-01\n---\n\nOne.',
      'two.md': '---\ntitle: Two\ndate: 2024-02-01\n---\n\nTwo.',
    });

    buildSite(fixture.contentDir, fixture.outputDir);

    const index = readFileSync(join(fixture.outputDir, 'index.html'), 'utf8');
    expect(index).toContain('href="one.html"');
    expect(index).toContain('href="two.html"');
    expect(index).toContain('>One</a>');
    expect(index).toContain('>Two</a>');
  });

  it('sorts pages by date descending on the index', () => {
    fixture = createFixture({
      'one.md': '---\ntitle: One\ndate: 2024-01-01\n---\n\nOne.',
      'two.md': '---\ntitle: Two\ndate: 2024-02-01\n---\n\nTwo.',
      'three.md': '---\ntitle: Three\ndate: 2024-03-01\n---\n\nThree.',
    });

    const pages = buildSite(fixture.contentDir, fixture.outputDir);
    expect(pages.map((p) => p.title)).toEqual(['Three', 'Two', 'One']);
  });

  it('recursively discovers markdown files in subdirectories', () => {
    fixture = createFixture({
      'nested/inner.md': '---\ntitle: Inner\n---\n\nInner content.',
    });

    const files = listMarkdownFiles(fixture.contentDir);
    expect(files).toHaveLength(1);

    buildSite(fixture.contentDir, fixture.outputDir);
    expect(existsSync(join(fixture.outputDir, 'inner.html'))).toBe(true);
  });

  it('creates the output directory when it does not exist', () => {
    fixture = createFixture({
      'post.md': '# No frontmatter',
    });

    buildSite(fixture.contentDir, fixture.outputDir);
    expect(existsSync(join(fixture.outputDir, 'index.html'))).toBe(true);
    expect(existsSync(join(fixture.outputDir, 'post.html'))).toBe(true);
  });

  it('falls back to the filename as the page title', () => {
    fixture = createFixture({
      'untitled.md': 'Just body text without frontmatter.',
    });

    const pages = buildSite(fixture.contentDir, fixture.outputDir);
    expect(pages[0].title).toBe('untitled');
  });
});
