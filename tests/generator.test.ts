import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { buildSite, findMarkdownFiles, loadPages } from '../src/generator';

function makeTmpDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
}

describe('findMarkdownFiles', () => {
  let contentDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir();
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  it('returns an empty array for a missing directory', () => {
    expect(findMarkdownFiles(path.join(contentDir, 'does-not-exist'))).toEqual([]);
  });

  it('finds .md files recursively and ignores other extensions', () => {
    fs.writeFileSync(path.join(contentDir, 'a.md'), '# A');
    fs.writeFileSync(path.join(contentDir, 'notes.txt'), 'ignore me');
    fs.mkdirSync(path.join(contentDir, 'nested'));
    fs.writeFileSync(path.join(contentDir, 'nested', 'b.markdown'), '# B');

    const files = findMarkdownFiles(contentDir).sort();

    expect(files).toEqual(['a.md', 'nested/b.markdown']);
  });
});

describe('loadPages', () => {
  let contentDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir();
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  it('parses every markdown file into a Page', () => {
    fs.writeFileSync(
      path.join(contentDir, 'first.md'),
      '---\ntitle: First\n---\nFirst body'
    );
    fs.writeFileSync(
      path.join(contentDir, 'second.md'),
      '---\ntitle: Second\n---\nSecond body'
    );

    const pages = loadPages(contentDir).sort((a, b) => a.slug.localeCompare(b.slug));

    expect(pages).toHaveLength(2);
    expect(pages[0].title).toBe('First');
    expect(pages[1].title).toBe('Second');
  });
});

describe('buildSite', () => {
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir();
    outputDir = makeTmpDir();
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('throws when the content directory does not exist', () => {
    expect(() =>
      buildSite({ contentDir: path.join(contentDir, 'missing'), outputDir })
    ).toThrow(/Content directory not found/);
  });

  it('writes a per-page HTML file and an index.html', () => {
    fs.writeFileSync(
      path.join(contentDir, 'about.md'),
      '---\ntitle: About\ndate: 2024-02-02\ntags: [meta]\n---\n# About us'
    );

    const result = buildSite({ contentDir, outputDir });

    expect(result.pages).toHaveLength(1);
    expect(fs.existsSync(path.join(outputDir, 'about.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);

    const pageHtml = fs.readFileSync(path.join(outputDir, 'about.html'), 'utf-8');
    expect(pageHtml).toContain('<h1>About</h1>');

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('href="about.html"');
    expect(indexHtml).toContain('About');
  });

  it('creates an empty index when there is no content', () => {
    const result = buildSite({ contentDir, outputDir });

    expect(result.pages).toEqual([]);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
  });

  it('preserves nested directory structure in the output', () => {
    fs.mkdirSync(path.join(contentDir, 'posts'));
    fs.writeFileSync(
      path.join(contentDir, 'posts', 'first-post.md'),
      '---\ntitle: First Post\n---\nBody'
    );

    buildSite({ contentDir, outputDir });

    expect(fs.existsSync(path.join(outputDir, 'posts', 'first-post.html'))).toBe(true);
  });
});

describe('buildSite with templatesDir', () => {
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir();
    outputDir = makeTmpDir();
    templatesDir = makeTmpDir();
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  function writeTemplateFile(relativePath: string, contents: string) {
    const filePath = path.join(templatesDir, relativePath);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, contents, 'utf-8');
  }

  it('renders pages through the default layout when no template is specified', () => {
    writeTemplateFile('layouts/default.hbs', '<div class="layout-default">{{{body}}}</div>');
    fs.writeFileSync(path.join(contentDir, 'about.md'), '---\ntitle: About\n---\n# About us');

    buildSite({ contentDir, outputDir, templatesDir });

    const html = fs.readFileSync(path.join(outputDir, 'about.html'), 'utf-8');
    expect(html).toContain('class="layout-default"');
    expect(html).toContain('<h1>About</h1>');
  });

  it('renders a page through the layout named in its frontmatter `template` field', () => {
    writeTemplateFile('layouts/default.hbs', '<div class="layout-default">{{{body}}}</div>');
    writeTemplateFile('layouts/post.hbs', '<div class="layout-post">{{{body}}}</div>');
    fs.writeFileSync(
      path.join(contentDir, 'post.md'),
      '---\ntitle: My Post\ntemplate: post\n---\nPost body'
    );
    fs.writeFileSync(path.join(contentDir, 'page.md'), '---\ntitle: Plain Page\n---\nPage body');

    buildSite({ contentDir, outputDir, templatesDir });

    const postHtml = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
    const pageHtml = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(postHtml).toContain('class="layout-post"');
    expect(pageHtml).toContain('class="layout-default"');
  });

  it('includes header/nav/footer partials in rendered pages', () => {
    writeTemplateFile('partials/header.hbs', '<header>SITE HEADER</header>');
    writeTemplateFile('partials/nav.hbs', '<nav>SITE NAV</nav>');
    writeTemplateFile('partials/footer.hbs', '<footer>SITE FOOTER</footer>');
    writeTemplateFile(
      'layouts/default.hbs',
      '{{> header}}{{> nav}}<main>{{{body}}}</main>{{> footer}}'
    );
    fs.writeFileSync(path.join(contentDir, 'about.md'), '---\ntitle: About\n---\nBody');

    buildSite({ contentDir, outputDir, templatesDir });

    const html = fs.readFileSync(path.join(outputDir, 'about.html'), 'utf-8');
    expect(html).toContain('SITE HEADER');
    expect(html).toContain('SITE NAV');
    expect(html).toContain('SITE FOOTER');
  });

  it('renders the index page through an "index" layout when present', () => {
    writeTemplateFile('layouts/index.hbs', '<div class="home">{{{body}}}</div>');
    fs.writeFileSync(path.join(contentDir, 'about.md'), '---\ntitle: About\n---\nBody');

    buildSite({ contentDir, outputDir, templatesDir });

    const html = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(html).toContain('class="home"');
    expect(html).toContain('href="about.html"');
  });

  it('falls back to the built-in renderer when templatesDir does not exist', () => {
    fs.writeFileSync(path.join(contentDir, 'about.md'), '---\ntitle: About\n---\nBody');
    fs.rmSync(templatesDir, { recursive: true, force: true });

    buildSite({ contentDir, outputDir, templatesDir });

    const html = fs.readFileSync(path.join(outputDir, 'about.html'), 'utf-8');
    expect(html).toContain('<h1>About</h1>');
    expect(html).toContain('<article>');
  });

  it('falls back to the built-in renderer for a page when no layouts exist at all', () => {
    fs.writeFileSync(path.join(contentDir, 'about.md'), '---\ntitle: About\n---\nBody');

    buildSite({ contentDir, outputDir, templatesDir });

    const html = fs.readFileSync(path.join(outputDir, 'about.html'), 'utf-8');
    expect(html).toContain('<article>');
  });
});
