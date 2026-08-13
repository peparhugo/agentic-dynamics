import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { build } from '../src/build';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-build-'));
}

describe('build', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    root = makeTempDir();
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
    fs.mkdirSync(contentDir);
  });

  afterEach(() => {
    fs.rmSync(root, { recursive: true, force: true });
  });

  it('generates an html file per markdown page plus an index', () => {
    fs.writeFileSync(
      path.join(contentDir, 'first.md'),
      '---\ntitle: First\ndate: 2026-01-01\n---\n\nFirst body.\n'
    );
    fs.writeFileSync(
      path.join(contentDir, 'second.md'),
      '---\ntitle: Second\ndate: 2026-02-01\n---\n\nSecond body.\n'
    );

    const result = build({ contentDir, outputDir });

    expect(result.pages).toHaveLength(2);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'first.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'second.html'))).toBe(true);

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('href="first.html"');
    expect(indexHtml).toContain('href="second.html"');

    const firstHtml = fs.readFileSync(path.join(outputDir, 'first.html'), 'utf-8');
    expect(firstHtml).toContain('First body.');
  });

  it('creates the output directory if it does not exist', () => {
    fs.writeFileSync(path.join(contentDir, 'only.md'), '# Only page');

    expect(fs.existsSync(outputDir)).toBe(false);
    build({ contentDir, outputDir });
    expect(fs.existsSync(outputDir)).toBe(true);
  });

  it('produces an empty index when there is no markdown content', () => {
    const result = build({ contentDir, outputDir });
    expect(result.pages).toHaveLength(0);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
  });

  it('throws when the content directory does not exist', () => {
    expect(() => build({ contentDir: path.join(root, 'missing'), outputDir })).toThrow(
      /Content directory not found/
    );
  });

  it('throws when two pages resolve to the same slug', () => {
    fs.writeFileSync(path.join(contentDir, 'My Post.md'), '# One');
    fs.writeFileSync(path.join(contentDir, 'my-post.md'), '# Two');

    expect(() => build({ contentDir, outputDir })).toThrow(/Duplicate page slug/);
  });

  it('falls back to the built-in default templates when templatesDir does not exist', () => {
    fs.writeFileSync(path.join(contentDir, 'only.md'), '---\ntitle: Only\n---\n\nOnly body.\n');

    const result = build({
      contentDir,
      outputDir,
      templatesDir: path.join(root, 'no-such-templates-dir'),
    });

    expect(result.pages).toHaveLength(1);
    const html = fs.readFileSync(path.join(outputDir, 'only.html'), 'utf-8');
    expect(html).toContain('<h1>Only</h1>');
    expect(html).toContain('Only body.');
  });

  describe('with a custom templates directory', () => {
    let templatesDir: string;

    beforeEach(() => {
      templatesDir = path.join(root, 'templates');
      fs.mkdirSync(path.join(templatesDir, 'layouts'), { recursive: true });
      fs.mkdirSync(path.join(templatesDir, 'partials'), { recursive: true });
      fs.writeFileSync(
        path.join(templatesDir, 'layouts', 'default.hbs'),
        '<html><head><title>{{title}}</title></head><body>{{> nav}}{{{body}}}</body></html>'
      );
      fs.writeFileSync(path.join(templatesDir, 'partials', 'nav.hbs'), '<nav>site-nav</nav>');
      fs.writeFileSync(
        path.join(templatesDir, 'page.hbs'),
        '<article>{{title}}: {{{content}}}</article>'
      );
      fs.writeFileSync(
        path.join(templatesDir, 'post.hbs'),
        '<article class="post">{{title}} (post): {{{content}}}</article>'
      );
    });

    it('renders pages with the default template and includes registered partials', () => {
      fs.writeFileSync(path.join(contentDir, 'default-page.md'), '---\ntitle: Default Page\n---\n\nHi.\n');

      build({ contentDir, outputDir, templatesDir });

      const html = fs.readFileSync(path.join(outputDir, 'default-page.html'), 'utf-8');
      expect(html).toContain('<nav>site-nav</nav>');
      expect(html).toContain('<article>Default Page:');
    });

    it('renders a page with the template named in its frontmatter', () => {
      fs.writeFileSync(
        path.join(contentDir, 'blog-post.md'),
        '---\ntitle: Blog Post\ntemplate: post\n---\n\nHello.\n'
      );

      build({ contentDir, outputDir, templatesDir });

      const html = fs.readFileSync(path.join(outputDir, 'blog-post.html'), 'utf-8');
      expect(html).toContain('<article class="post">Blog Post (post):');
    });
  });
});
