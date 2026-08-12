import fs from 'fs';
import os from 'os';
import path from 'path';
import { buildSite } from './build';
import { createTemplateEngine } from './templates';
import { Page } from './types';

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'about',
    content: '# About',
    html: '<h1>About</h1>',
    data: {},
    ...overrides,
  };
}

function makeTemplates(root: string, files: Record<string, string>): string {
  const dir = path.join(root, 'templates');
  for (const [rel, content] of Object.entries(files)) {
    const full = path.join(dir, rel);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, content, 'utf-8');
  }
  return dir;
}

function withTemp(fn: (root: string) => void): void {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));
  try {
    fn(root);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

describe('createTemplateEngine', () => {
  it('throws when the templates directory does not exist', () => {
    withTemp((root) => {
      expect(() => createTemplateEngine(path.join(root, 'nope'))).toThrow('does not exist');
    });
  });
});

describe('TemplateEngine.renderPage', () => {
  it('uses the template named in frontmatter', () => {
    withTemp((root) => {
      const dir = makeTemplates(root, {
        'layouts/base.hbs': 'BASE{{{body}}}',
        'default.hbs': 'DEFAULT[{{{html}}}]',
        'post.hbs': 'POST[{{{html}}}]',
      });
      const engine = createTemplateEngine(dir);
      const page = makePage({ data: { template: 'post' } });
      expect(engine.renderPage(page)).toBe('BASEPOST[<h1>About</h1>]');
    });
  });

  it('falls back to the default template when none is specified', () => {
    withTemp((root) => {
      const dir = makeTemplates(root, {
        'layouts/base.hbs': 'BASE{{{body}}}',
        'default.hbs': 'DEFAULT[{{{html}}}]',
      });
      const engine = createTemplateEngine(dir);
      expect(engine.renderPage(makePage())).toBe('BASEDEFAULT[<h1>About</h1>]');
    });
  });

  it('falls back to the default template when the named one is missing', () => {
    withTemp((root) => {
      const dir = makeTemplates(root, {
        'layouts/base.hbs': 'BASE{{{body}}}',
        'default.hbs': 'DEFAULT[{{{html}}}]',
      });
      const engine = createTemplateEngine(dir);
      expect(engine.renderPage(makePage({ data: { template: 'missing' } }))).toBe(
        'BASEDEFAULT[<h1>About</h1>]'
      );
    });
  });

  it('returns undefined when neither the named nor the default template exists', () => {
    withTemp((root) => {
      const dir = makeTemplates(root, {
        'layouts/base.hbs': 'BASE{{{body}}}',
        'post.hbs': 'POST',
      });
      const engine = createTemplateEngine(dir);
      expect(engine.renderPage(makePage())).toBeUndefined();
    });
  });

  it('wraps template output in the layout with the {{{body}}} placeholder', () => {
    withTemp((root) => {
      const dir = makeTemplates(root, {
        'layouts/base.hbs': '<html><body>{{{body}}}</body></html>',
        'default.hbs': '<article>{{{html}}}</article>',
      });
      const engine = createTemplateEngine(dir);
      const html = engine.renderPage(makePage()) ?? '';
      expect(html).toContain('<article>');
      expect(html).toBe('<html><body><article><h1>About</h1></article></body></html>');
    });
  });

  it('uses the layout named in frontmatter', () => {
    withTemp((root) => {
      const dir = makeTemplates(root, {
        'layouts/base.hbs': 'BASE{{{body}}}',
        'layouts/narrow.hbs': 'NARROW{{{body}}}',
        'default.hbs': 'DEFAULT[{{{html}}}]',
      });
      const engine = createTemplateEngine(dir);
      const page = makePage({ data: { layout: 'narrow' } });
      expect(engine.renderPage(page)).toBe('NARROWDEFAULT[<h1>About</h1>]');
    });
  });

  it('renders partials (header, footer, nav) from templates/layouts', () => {
    withTemp((root) => {
      const dir = makeTemplates(root, {
        'layouts/base.hbs': 'P{{> header}}~{{> nav}}~{{> footer}}{{{body}}}',
        'partials/header.hbs': 'H',
        'partials/nav.hbs': 'N',
        'partials/footer.hbs': 'F',
        'default.hbs': 'DEFAULT[{{{html}}}]',
      });
      const engine = createTemplateEngine(dir);
      expect(engine.renderPage(makePage())).toBe('PH~N~FDEFAULT[<h1>About</h1>]');
    });
  });
});

describe('TemplateEngine.renderIndex', () => {
  it('renders the index template with the list of pages', () => {
    withTemp((root) => {
      const dir = makeTemplates(root, {
        'layouts/base.hbs': 'BASE{{{body}}}',
        'index.hbs': 'LIST[{{#each pages}}<{{slug}}>{{title}}{{/each}}]',
      });
      const engine = createTemplateEngine(dir);
      const pages = [
        makePage({ slug: 'a', data: { title: 'A' } }),
        makePage({ slug: 'b', data: { title: 'B' } }),
      ];
      expect(engine.renderIndex(pages)).toBe('BASELIST[<a>A<b>B]');
    });
  });
});

describe('buildSite with templates', () => {
  it('uses templates, layout and partials when a templates directory exists', () => {
    withTemp((root) => {
      const contentDir = path.join(root, 'content');
      const outputDir = path.join(root, 'dist');
      fs.mkdirSync(contentDir);
      fs.writeFileSync(
        path.join(contentDir, 'about.md'),
        '---\ntitle: About\n---\n\nAbout **us**.',
        'utf-8'
      );
      const templatesDir = makeTemplates(root, {
        'layouts/base.hbs': 'BASE{{{body}}}',
        'partials/header.hbs': 'HEADER',
        'partials/footer.hbs': 'FOOTER',
        'partials/nav.hbs': 'NAV',
        'default.hbs': '<h1>{{title}}</h1>{{> header}}{{{html}}}',
        'index.hbs': 'INDEX[{{#each pages}}{{title}};{{/each}}]',
      });

      const pages = buildSite({ contentDir, outputDir, templatesDir });

      expect(pages).toHaveLength(1);
      const about = fs.readFileSync(path.join(outputDir, 'about.html'), 'utf-8');
      expect(about).toContain('BASE');
      expect(about).toContain('HEADER');
      expect(about).toContain('<h1>About</h1>');
      expect(about).toContain('<strong>us</strong>');

      const index = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
      expect(index).toContain('BASEINDEX[About;]');
    });
  });

  it('renders each page with the template named in its frontmatter', () => {
    withTemp((root) => {
      const contentDir = path.join(root, 'content');
      const outputDir = path.join(root, 'dist');
      fs.mkdirSync(contentDir);
      fs.writeFileSync(
        path.join(contentDir, 'plain.md'),
        '---\ntitle: Plain\n---\n\nplain body.',
        'utf-8'
      );
      fs.writeFileSync(
        path.join(contentDir, 'special.md'),
        '---\ntitle: Special\ntemplate: special\n---\n\nspecial body.',
        'utf-8'
      );
      const templatesDir = makeTemplates(root, {
        'default.hbs': 'DEFAULT[{{{html}}}]',
        'special.hbs': 'SPECIAL[{{{html}}}]',
      });

      buildSite({ contentDir, outputDir, templatesDir });

      expect(fs.readFileSync(path.join(outputDir, 'plain.html'), 'utf-8')).toContain(
        'DEFAULT[<p>plain body.</p>'
      );
      expect(fs.readFileSync(path.join(outputDir, 'special.html'), 'utf-8')).toContain(
        'SPECIAL[<p>special body.</p>'
      );
    });
  });

  it('falls back to built-in rendering when no templates directory exists', () => {
    withTemp((root) => {
      const contentDir = path.join(root, 'content');
      const outputDir = path.join(root, 'dist');
      fs.mkdirSync(contentDir);
      fs.writeFileSync(path.join(contentDir, 'page.md'), '---\ntitle: Page\n---\n\nBody.', 'utf-8');

      const pages = buildSite({ contentDir, outputDir, templatesDir: path.join(root, 'templates') });

      expect(pages).toHaveLength(1);
      const html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<nav><a href="index.html">Home</a></nav>');
    });
  });
});
