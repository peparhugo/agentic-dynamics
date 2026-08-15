import fs from 'fs';
import os from 'os';
import path from 'path';
import { build, buildPage, TemplateEngine, formatDate } from '../src';

function tmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('TemplateEngine', () => {
  it('renders a page with the default template and layout', () => {
    const dir = tmpDir('ssg-tpl-');
    try {
      const engine = new TemplateEngine(dir);
      const page = buildPage('hello', '---\ntitle: Hello\n---\n# Hi\n');
      const html = engine.renderPage(page, [page]);
      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<h1>Hello</h1>');
      expect(html).toContain('<h1>Hi</h1>');
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('uses a template specified in frontmatter', () => {
    const dir = tmpDir('ssg-tpl-');
    try {
      fs.mkdirSync(path.join(dir, 'layouts'), { recursive: true });
      fs.writeFileSync(
        path.join(dir, 'fancy.hbs'),
        '<section class="fancy">{{{html}}}</section>'
      );
      fs.writeFileSync(
        path.join(dir, 'layouts', 'default.hbs'),
        '<html><body>{{{body}}}</body></html>'
      );
      const engine = new TemplateEngine(dir);
      const page = buildPage('x', '---\ntitle: X\ntemplate: fancy\n---\n# Hi\n');
      const html = engine.renderPage(page, [page]);
      expect(html).toContain('<section class="fancy">');
      expect(html).toContain('<h1>Hi</h1>');
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('wraps content in a layout specified in frontmatter', () => {
    const dir = tmpDir('ssg-tpl-');
    try {
      fs.mkdirSync(path.join(dir, 'layouts'), { recursive: true });
      fs.writeFileSync(
        path.join(dir, 'layouts', 'wide.hbs'),
        '<html><body><div id="wrap">{{{body}}}</div></body></html>'
      );
      const engine = new TemplateEngine(dir);
      const page = buildPage('x', '---\ntitle: X\nlayout: wide\n---\n# Hi\n');
      const html = engine.renderPage(page, [page]);
      expect(html).toContain('<div id="wrap">');
      expect(html).toContain('<h1>X</h1>');
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('includes partials from the partials directory', () => {
    const dir = tmpDir('ssg-tpl-');
    try {
      fs.mkdirSync(path.join(dir, 'partials'), { recursive: true });
      fs.mkdirSync(path.join(dir, 'layouts'), { recursive: true });
      fs.writeFileSync(
        path.join(dir, 'partials', 'header.hbs'),
        '<header id="site-header">Header</header>'
      );
      fs.writeFileSync(path.join(dir, 'page.hbs'), '{{> header}}<main>{{{html}}}</main>');
      fs.writeFileSync(
        path.join(dir, 'layouts', 'default.hbs'),
        '<html><body>{{{body}}}</body></html>'
      );
      const engine = new TemplateEngine(dir);
      const page = buildPage('x', '---\ntitle: X\n---\n# Hi\n');
      const html = engine.renderPage(page, [page]);
      expect(html).toContain('<header id="site-header">Header</header>');
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('renders the index with links to every page', () => {
    const dir = tmpDir('ssg-tpl-');
    try {
      const engine = new TemplateEngine(dir);
      const pages = [
        buildPage('b', '---\ntitle: B\ndate: 2024-02-01\n---\n# B\n'),
        buildPage('a', '---\ntitle: A\ndate: 2024-01-01\n---\n# A\n'),
      ];
      const html = engine.renderIndex(pages);
      expect(html).toContain('<a href="b.html">B</a>');
      expect(html).toContain('<a href="a.html">A</a>');
      expect(html.indexOf('b.html')).toBeLessThan(html.indexOf('a.html'));
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('throws when a specified template is missing', () => {
    const dir = tmpDir('ssg-tpl-');
    try {
      const engine = new TemplateEngine(dir);
      const page = buildPage('x', '---\ntitle: X\ntemplate: nope\n---\n# Hi\n');
      expect(() => engine.renderPage(page, [page])).toThrow(/Template not found/);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it('throws when a specified layout is missing', () => {
    const dir = tmpDir('ssg-tpl-');
    try {
      const engine = new TemplateEngine(dir);
      const page = buildPage('x', '---\ntitle: X\nlayout: nope\n---\n# Hi\n');
      expect(() => engine.renderPage(page, [page])).toThrow(/Layout not found/);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe('build with templates', () => {
  it('applies custom templates and layouts end-to-end', () => {
    const content = tmpDir('ssg-content-');
    const out = tmpDir('ssg-out-');
    const tpl = tmpDir('ssg-templates-');
    try {
      fs.mkdirSync(path.join(tpl, 'layouts'), { recursive: true });
      fs.mkdirSync(path.join(tpl, 'partials'), { recursive: true });
      fs.writeFileSync(path.join(tpl, 'partials', 'nav.hbs'), '<nav id="nav">Nav</nav>');
      fs.writeFileSync(
        path.join(tpl, 'custom.hbs'),
        '{{> nav}}<article class="custom">{{title}}</article>'
      );
      fs.writeFileSync(
        path.join(tpl, 'layouts', 'default.hbs'),
        '<html><body>{{{body}}}</body></html>'
      );

      fs.writeFileSync(
        path.join(content, 'a.md'),
        '---\ntitle: Custom Post\ntemplate: custom\n---\n# Body\n'
      );

      build({ contentDir: content, outputDir: out, templatesDir: tpl });

      const html = fs.readFileSync(path.join(out, 'a.html'), 'utf-8');
      expect(html).toContain('<nav id="nav">Nav</nav>');
      expect(html).toContain('<article class="custom">Custom Post</article>');
      expect(html).not.toContain('{{{body}}}');
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(out, { recursive: true, force: true });
      fs.rmSync(tpl, { recursive: true, force: true });
    }
  });
});

describe('formatDate', () => {
  it('returns ISO date or empty string', () => {
    expect(formatDate(new Date(0))).toBe('');
    expect(formatDate(new Date('2024-06-15'))).toBe('2024-06-15');
  });
});
