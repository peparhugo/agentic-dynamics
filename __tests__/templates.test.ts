import { spawnSync } from 'child_process';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { parseArgs } from '../src/cli';
import { buildSite } from '../src/generator';
import { TemplateEngine } from '../src/templates';
import type { Page } from '../src/types';

const REPO_ROOT = path.resolve(__dirname, '..');
const CLI_JS = path.join(REPO_ROOT, 'dist', 'cli.js');

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeContent(dir: string, files: Record<string, string>): void {
  fs.mkdirSync(dir, { recursive: true });
  for (const [name, content] of Object.entries(files)) {
    const filePath = path.join(dir, name);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, content);
  }
}

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'page',
    title: 'Page',
    contentHtml: '<p>Body</p>',
    content: 'Body',
    ...overrides,
  };
}

function defaultTemplateDir(): string {
  const tmp = makeTempDir('ssg-tpl-');
  const tplDir = path.join(tmp, 'templates');
  writeContent(tplDir, {
    'default.hbs': '{{> header}}\n<article>{{title}}|{{{body}}}</article>',
    'post.hbs': '<p>{{title}}</p>',
    'show.hbs': '<div data-author="{{author}}">{{{contentHtml}}}</div>',
    'layouts/default.hbs': [
      '<html>',
      '<head><title>{{title}}</title></head>',
      '<body>',
      '{{> header}}',
      '{{{body}}}',
      '{{> footer}}',
      '</body>',
      '</html>',
    ].join('\n'),
    'layouts/empty.hbs': 'EMPTY',
    'partials/header.hbs': '<header>Site Header</header>',
    'partials/footer.hbs': '<footer>Site Footer</footer>',
  });
  return tplDir;
}

describe('TemplateEngine directory structure', () => {
  it('loads templates, layouts and partials from their directories', () => {
    const engine = new TemplateEngine({ templateDir: defaultTemplateDir() });
    engine.load();
    expect(engine.getTemplateNames()).toEqual(['default', 'post', 'show']);
    expect(engine.getLayoutNames()).toEqual(['default', 'empty']);
    expect(engine.getPartialNames()).toEqual(expect.arrayContaining(['header', 'footer']));
    expect(engine.hasContent()).toBe(true);
    expect(engine.hasTemplate('post')).toBe(true);
    expect(engine.hasTemplate('nope')).toBe(false);
    expect(engine.hasLayout('default')).toBe(true);
    expect(engine.defaultTemplate).toBe('default');
    expect(engine.defaultLayout).toBe('default');
  });

  it('treats a missing template directory as empty', () => {
    const tmp = makeTempDir('ssg-tpl-none-');
    const engine = new TemplateEngine({ templateDir: path.join(tmp, 'missing') });
    engine.load();
    expect(engine.hasContent()).toBe(false);
    expect(engine.getTemplateNames()).toEqual([]);
    expect(engine.getLayoutNames()).toEqual([]);
    expect(engine.getPartialNames()).toEqual([]);
  });
});

describe('TemplateEngine.renderPage', () => {
  it('uses the default template and layout with partials and {{{body}}}', () => {
    const engine = new TemplateEngine({ templateDir: defaultTemplateDir() });
    const page = makePage({ title: 'Hello' });
    const html = engine.renderPage(page);
    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('<header>Site Header</header>');
    expect(html).toContain('<footer>Site Footer</footer>');
    expect(html).toContain('<article>Hello|<p>Body</p></article>');
  });

  it('uses the template selected by the page frontmatter', () => {
    const engine = new TemplateEngine({ templateDir: defaultTemplateDir() });
    const page = makePage({ template: 'post', title: 'Post' });
    const html = engine.renderPage(page);
    expect(html).toContain('<p>Post</p>');
    expect(html).not.toContain('<article>');
  });

  it('uses the layout selected by the page frontmatter', () => {
    const engine = new TemplateEngine({ templateDir: defaultTemplateDir() });
    const page = makePage({ layout: 'empty' });
    expect(engine.renderPage(page)).toBe('EMPTY');
  });

  it('passes frontmatter data and renders it HTML-escaped', () => {
    const engine = new TemplateEngine({ templateDir: defaultTemplateDir() });
    const page = makePage({
      template: 'show',
      data: { author: 'Jane & Co' },
      contentHtml: '<b>Hi</b>',
    });
    const html = engine.renderPage(page);
    expect(html).toContain('data-author="Jane &amp; Co"');
    expect(html).toContain('<b>Hi</b>');
  });

  it('throws when the selected template is missing', () => {
    const engine = new TemplateEngine({ templateDir: defaultTemplateDir() });
    const page = makePage({ template: 'does-not-exist' });
    expect(() => engine.renderPage(page)).toThrow(/Template not found: "does-not-exist"/);
  });

  it('throws when the selected layout is missing', () => {
    const engine = new TemplateEngine({ templateDir: defaultTemplateDir() });
    const page = makePage({ layout: 'does-not-exist' });
    expect(() => engine.renderPage(page)).toThrow(/Layout not found: "does-not-exist"/);
  });

  it('wraps built-in body in a layout when no page template is configured', () => {
    const tmp = makeTempDir('ssg-tpl-layoutonly-');
    const tplDir = path.join(tmp, 'templates');
    writeContent(tplDir, {
      'layouts/base.hbs': '<html><body>{{> nav}}{{{body}}}</body></html>',
      'partials/nav.hbs': '<nav>N</nav>',
    });
    const engine = new TemplateEngine({ templateDir: tplDir, defaultLayout: 'base' });
    const html = engine.renderPage(makePage({ title: 'Only' }));
    expect(html).toContain('<nav>N</nav>');
    expect(html).toContain('<h1>Only</h1>');
    expect(html).toContain('<p>Body</p>');
  });
});

describe('buildSite with templates', () => {
  function buildWithTemplates(files: { templates: Record<string, string>; content: Record<string, string> }) {
    const tmp = makeTempDir('ssg-tpl-build-');
    const contentDir = path.join(tmp, 'content');
    const outputDir = path.join(tmp, 'dist');
    const tplDir = path.join(tmp, 'templates');
    writeContent(tplDir, files.templates);
    writeContent(contentDir, files.content);
    const pages = buildSite({ contentDir, outputDir, templateDir: tplDir });
    return { tmp, contentDir, outputDir, tplDir, pages };
  }

  it('renders pages through the default template, layout and partials', () => {
    const { outputDir, pages } = buildWithTemplates({
      templates: {
        'default.hbs': '<h1>{{title}}</h1>\n{{{contentHtml}}}',
        'layouts/default.hbs': [
          '<!DOCTYPE html>',
          '<html><head><title>{{title}}</title></head><body>',
          '{{> nav}}',
          '{{{body}}}',
          '</body></html>',
        ].join('\n'),
        'partials/nav.hbs': '<nav>Home</nav>',
      },
      content: {
        'one.md': '---\ntitle: One\n---\n\n# One\n\nBody **one**.',
      },
    });

    expect(pages.map((p) => p.slug)).toEqual(['one']);
    const one = fs.readFileSync(path.join(outputDir, 'one.html'), 'utf8');
    expect(one).toContain('<nav>Home</nav>');
    expect(one).toContain('<title>One</title>');
    expect(one).toContain('<h1>One</h1>');
    expect(one).toContain('Body <strong>one</strong>');
  });

  it('uses per-page templates from frontmatter and renders a themed index', () => {
    const { outputDir, pages } = buildWithTemplates({
      templates: {
        'default.hbs': '<main>{{{contentHtml}}}</main>',
        'post.hbs': '<article class="post">{{{contentHtml}}}</article>',
        'index.hbs': [
          '<h1>Index</h1>',
          '<ul>',
          '{{#each pages}}',
          '<li><a href="{{slug}}.html">{{title}}</a></li>',
          '{{/each}}',
          '</ul>',
        ].join('\n'),
        'layouts/default.hbs': '<html><body>{{{body}}}</body></html>',
        'partials/footer.hbs': '<footer>F</footer>',
      },
      content: {
        'a.md': '---\ntitle: Alpha\n---\n\n# Alpha',
        'b.md': '---\ntitle: Beta\ntemplate: post\n---\n\n# Beta',
      },
    });

    expect(pages.map((p) => p.slug).sort()).toEqual(['a', 'b']);
    const a = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');
    expect(a).toContain('<main>');
    const b = fs.readFileSync(path.join(outputDir, 'b.html'), 'utf8');
    expect(b).toContain('<article class="post">');
    const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf8');
    expect(index).toContain('<a href="a.html">Alpha</a>');
    expect(index).toContain('<a href="b.html">Beta</a>');
  });

  it('exposes custom frontmatter fields to templates', () => {
    const { outputDir } = buildWithTemplates({
      templates: {
        'default.hbs': '<aside>{{author}}</aside>\n{{{contentHtml}}}',
        'layouts/default.hbs': '<html><body>{{{body}}}</body></html>',
      },
      content: {
        'a.md': '---\ntitle: A\nauthor: Jane\n---\n\n# A',
      },
    });
    expect(fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8')).toContain('<aside>Jane</aside>');
  });

  it('throws when an explicit template directory does not exist', () => {
    const tmp = makeTempDir('ssg-tpl-missing-');
    const contentDir = path.join(tmp, 'content');
    fs.mkdirSync(contentDir, { recursive: true });
    expect(() =>
      buildSite({
        contentDir,
        outputDir: path.join(tmp, 'dist'),
        templateDir: path.join(tmp, 'no-templates'),
      })
    ).toThrow(/Template directory does not exist/);
  });

  it('keeps built-in rendering when no template directory is present', () => {
    const tmp = makeTempDir('ssg-tpl-none-');
    const contentDir = path.join(tmp, 'content');
    const outputDir = path.join(tmp, 'dist');
    writeContent(contentDir, { 'a.md': '---\ntitle: A\n---\n\n# A' });
    buildSite({ contentDir, outputDir });
    const html = fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>A</title>');
  });
});

describe('CLI templates option', () => {
  function ensureBuilt(): void {
    if (!fs.existsSync(CLI_JS)) {
      const result = spawnSync('npx', ['tsc'], { cwd: REPO_ROOT, encoding: 'utf8' });
      if (result.status !== 0) {
        throw new Error(`Failed to build TypeScript: ${result.stderr}`);
      }
    }
  }

  beforeAll(() => {
    ensureBuilt();
  });

  it('parses the --templates option', () => {
    const opts = parseArgs(['build', '--templates', 'theme']);
    expect(opts.templateDir).toBe('theme');
  });

  it('renders the site with templates via the CLI binary', () => {
    const tmp = makeTempDir('ssg-tpl-cli-');
    const contentDir = path.join(tmp, 'content');
    const outputDir = path.join(tmp, 'dist');
    const tplDir = path.join(tmp, 'templates');
    writeContent(tplDir, {
      'default.hbs': '<h1>{{title}}</h1>\n{{{contentHtml}}}',
      'layouts/default.hbs': '<html><body>{{> header}}{{{body}}}</body></html>',
      'partials/header.hbs': '<header>CLI</header>',
    });
    writeContent(contentDir, { 'post.md': '---\ntitle: Post\n---\n\n# Post\n' });

    const result = spawnSync(
      process.execPath,
      [CLI_JS, 'build', '--content', contentDir, '--output', outputDir, '--templates', tplDir],
      { cwd: REPO_ROOT, encoding: 'utf8' }
    );

    expect(result.status).toBe(0);
    const html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf8');
    expect(html).toContain('<header>CLI</header>');
    expect(html).toContain('<h1>Post</h1>');
  });
});
