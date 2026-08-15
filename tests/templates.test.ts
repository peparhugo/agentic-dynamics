import fs from 'fs';
import os from 'os';
import path from 'path';
import { build } from '../src/ssg';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));
}

function writeFile(dir: string, name: string, content: string): string {
  const filePath = path.join(dir, name);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content);
  return filePath;
}

interface Fixture {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  cleanup(): void;
}

function makeFixture(): Fixture {
  const root = makeTempDir();
  const contentDir = path.join(root, 'content');
  const outputDir = path.join(root, 'dist');
  const templatesDir = path.join(root, 'templates');
  fs.mkdirSync(contentDir, { recursive: true });

  return {
    contentDir,
    outputDir,
    templatesDir,
    cleanup() {
      fs.rmSync(root, { recursive: true, force: true });
    },
  };
}

describe('template engine', () => {
  let fx: Fixture;

  beforeEach(() => {
    fx = makeFixture();
  });

  afterEach(() => {
    fx.cleanup();
  });

  it('renders a page with a custom template, layout, and partials', () => {
    writeFile(fx.templatesDir, 'layouts/default.hbs', [
      '<!DOCTYPE html>',
      '<html>',
      '<head><title>{{title}}</title></head>',
      '<body>',
      '{{> header}}',
      '{{> nav}}',
      '{{{body}}}',
      '{{> footer}}',
      '</body>',
      '</html>',
      '',
    ].join('\n'));

    writeFile(fx.templatesDir, 'partials/header.hbs', '<header>Header</header>');
    writeFile(fx.templatesDir, 'partials/nav.hbs', '<nav>Nav</nav>');
    writeFile(fx.templatesDir, 'partials/footer.hbs', '<footer>Footer</footer>');

    writeFile(fx.templatesDir, 'post.hbs', [
      '---',
      'layout: default',
      '---',
      '<article>',
      '<h1>{{title}}</h1>',
      '{{{body}}}',
      '</article>',
      '',
    ].join('\n'));

    writeFile(fx.contentDir, 'hello.md', [
      '---',
      'title: Hello',
      'template: post',
      '---',
      '',
      'Some **content**.',
    ].join('\n'));

    build({ contentDir: fx.contentDir, outputDir: fx.outputDir, templatesDir: fx.templatesDir });

    const html = fs.readFileSync(path.join(fx.outputDir, 'hello.html'), 'utf-8');
    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('<header>Header</header>');
    expect(html).toContain('<nav>Nav</nav>');
    expect(html).toContain('<footer>Footer</footer>');
    expect(html).toContain('<article>');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('<strong>content</strong>');
  });

  it('falls back to the default template when none is specified', () => {
    writeFile(fx.templatesDir, 'layouts/default.hbs', [
      '<main>{{{body}}}</main>',
      '',
    ].join('\n'));

    writeFile(fx.templatesDir, 'default.hbs', [
      '<article class="default">{{{body}}}</article>',
      '',
    ].join('\n'));

    writeFile(fx.contentDir, 'plain.md', 'Just a body.\n');

    build({ contentDir: fx.contentDir, outputDir: fx.outputDir, templatesDir: fx.templatesDir });

    const html = fs.readFileSync(path.join(fx.outputDir, 'plain.html'), 'utf-8');
    expect(html).toContain('<main>');
    expect(html).toContain('<article class="default">');
    expect(html).toContain('<p>Just a body.</p>');
  });

  it('wraps pages in the default layout when no template exists', () => {
    writeFile(fx.templatesDir, 'layouts/default.hbs', [
      '<!DOCTYPE html>',
      '<html>',
      '<head><title>{{title}}</title></head>',
      '<body>{{{body}}}</body>',
      '</html>',
      '',
    ].join('\n'));

    writeFile(fx.contentDir, 'hello.md', '---\ntitle: Hello\n---\n\nBody text.\n');

    build({ contentDir: fx.contentDir, outputDir: fx.outputDir, templatesDir: fx.templatesDir });

    const html = fs.readFileSync(path.join(fx.outputDir, 'hello.html'), 'utf-8');
    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('<p>Body text.</p>');
  });

  it('lets the page frontmatter override the layout declared by the template', () => {
    writeFile(fx.templatesDir, 'layouts/default.hbs', '<main>DEFAULT LAYOUT: {{{body}}}</main>');
    writeFile(fx.templatesDir, 'layouts/alt.hbs', '<main>ALT LAYOUT: {{{body}}}</main>');

    writeFile(fx.templatesDir, 'post.hbs', [
      '---',
      'layout: default',
      '---',
      '<article>{{{body}}}</article>',
      '',
    ].join('\n'));

    writeFile(fx.contentDir, 'hello.md', [
      '---',
      'title: Hello',
      'template: post',
      'layout: alt',
      '---',
      '',
      'Body text.',
    ].join('\n'));

    build({ contentDir: fx.contentDir, outputDir: fx.outputDir, templatesDir: fx.templatesDir });

    const html = fs.readFileSync(path.join(fx.outputDir, 'hello.html'), 'utf-8');
    expect(html).toContain('ALT LAYOUT:');
    expect(html).not.toContain('DEFAULT LAYOUT:');
  });

  it('renders a template without a layout unwrapped', () => {
    writeFile(fx.templatesDir, 'standalone.hbs', '<section>{{{body}}}</section>');

    writeFile(fx.contentDir, 'hello.md', '---\ntemplate: standalone\n---\n\nBody text.\n');

    build({ contentDir: fx.contentDir, outputDir: fx.outputDir, templatesDir: fx.templatesDir });

    const html = fs.readFileSync(path.join(fx.outputDir, 'hello.html'), 'utf-8');
    expect(html).toContain('<section>');
    expect(html).toContain('<p>Body text.</p>');
    expect(html).not.toContain('<main>');
  });

  it('resolves a template specified with its file extension', () => {
    writeFile(fx.templatesDir, 'post.hbs', '<article>{{{body}}}</article>');
    writeFile(fx.contentDir, 'hello.md', '---\ntemplate: post.hbs\n---\n\nBody text.\n');

    build({ contentDir: fx.contentDir, outputDir: fx.outputDir, templatesDir: fx.templatesDir });

    const html = fs.readFileSync(path.join(fx.outputDir, 'hello.html'), 'utf-8');
    expect(html).toContain('<article>');
  });

  it('escapes double-stache variables and keeps triple-stache body raw', () => {
    writeFile(fx.templatesDir, 'layouts/default.hbs', '<h1>{{title}}</h1>{{{body}}}');
    writeFile(fx.contentDir, 'hello.md', '---\ntitle: <script>alert(1)</script>\n---\n\n**bold**\n');

    build({ contentDir: fx.contentDir, outputDir: fx.outputDir, templatesDir: fx.templatesDir });

    const html = fs.readFileSync(path.join(fx.outputDir, 'hello.html'), 'utf-8');
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain('<strong>bold</strong>');
  });

  it('falls back to the built-in renderer when the templates directory does not exist', () => {
    writeFile(fx.contentDir, 'hello.md', '---\ntitle: Hello\n---\n\nBody text.\n');

    build({
      contentDir: fx.contentDir,
      outputDir: fx.outputDir,
      templatesDir: path.join(fx.templatesDir, 'missing'),
    });

    const html = fs.readFileSync(path.join(fx.outputDir, 'hello.html'), 'utf-8');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('<article>');
  });
});
