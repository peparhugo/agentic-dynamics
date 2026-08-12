import fs from 'fs/promises';
import os from 'os';
import path from 'path';
import {
  isTemplateFile,
  registerPartials,
  renderPageTemplate,
  renderLayout,
  renderPageWithTemplates,
  templateDirExists,
} from '../template';
import { buildSite } from '../build';
import { parseFrontmatter } from '../markdown';
import { Page } from '../types';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-template-'));
}

async function write(filePath: string, content: string): Promise<void> {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, content, 'utf-8');
}

function makePage(overrides: Partial<Page> = {}): Page {
  return {
    slug: 'hello',
    source: 'hello.md',
    title: 'Hello World',
    tags: ['intro', 'demo'],
    body: 'Hello **world**.',
    html: '<p>Hello <strong>world</strong>.</p>',
    ...overrides,
  };
}

describe('isTemplateFile', () => {
  it('recognizes .hbs and .handlebars files', () => {
    expect(isTemplateFile('layout.hbs')).toBe(true);
    expect(isTemplateFile('nav.handlebars')).toBe(true);
    expect(isTemplateFile('page.html')).toBe(false);
    expect(isTemplateFile('notes.hbs~')).toBe(false);
  });
});

describe('templateDirExists', () => {
  it('reports whether a template directory exists', async () => {
    const dir = await makeTempDir();
    await fs.mkdir(path.join(dir, 'templates'), { recursive: true });
    await expect(templateDirExists(path.join(dir, 'templates'))).resolves.toBe(true);
    await expect(templateDirExists(path.join(dir, 'missing'))).resolves.toBe(false);
  });
});

describe('registerPartials', () => {
  it('registers each .hbs file in the partials directory', async () => {
    const root = await makeTempDir();
    const templateDir = path.join(root, 'templates');
    await write(path.join(templateDir, 'partials', 'header.hbs'), '<header>Site</header>');
    await write(path.join(templateDir, 'partials', 'footer.hbs'), '<footer>End</footer>');
    await write(path.join(templateDir, 'partials', 'notes.txt'), 'not a partial');

    await registerPartials(templateDir);

    const { default: Handlebars } = await import('handlebars');
    const html = Handlebars.compile('{{> header}}{{> footer}}')({});
    expect(html).toContain('<header>Site</header>');
    expect(html).toContain('<footer>End</footer>');
  });

  it('is a no-op when the partials directory is missing', async () => {
    const root = await makeTempDir();
    const templateDir = path.join(root, 'templates');
    await expect(registerPartials(templateDir)).resolves.toBeUndefined();
  });
});

describe('renderPageTemplate', () => {
  it('uses the template named in the frontmatter', async () => {
    const root = await makeTempDir();
    const templateDir = path.join(root, 'templates');
    await write(
      path.join(templateDir, 'blog.hbs'),
      '<article class="blog">{{{body}}}</article>'
    );
    const page = makePage({ template: 'blog', html: '<p>Post content.</p>' });

    const html = await renderPageTemplate(page, templateDir);
    expect(html).toBe('<article class="blog"><p>Post content.</p></article>');
  });

  it('falls back to the default template when none is specified', async () => {
    const root = await makeTempDir();
    const templateDir = path.join(root, 'templates');
    await write(path.join(templateDir, 'default.hbs'), '<main>{{{body}}}</main>');
    const page = makePage({ template: undefined, html: '<p>Hi.</p>' });

    const html = await renderPageTemplate(page, templateDir);
    expect(html).toBe('<main><p>Hi.</p></main>');
  });

  it('renders the built-in default when the template file is missing', async () => {
    const root = await makeTempDir();
    const templateDir = path.join(root, 'templates');
    await write(path.join(templateDir, 'unrelated.hbs'), 'unused');

    const html = await renderPageTemplate(makePage(), templateDir);
    expect(html).toContain('<h1>Hello World</h1>');
    expect(html).toContain('class="tag">intro');
    expect(html).toContain('<strong>world</strong>');
  });

  it('escapes {{title}} but renders {{{body}}} unescaped', async () => {
    const root = await makeTempDir();
    const templateDir = path.join(root, 'templates');
    await write(
      path.join(templateDir, 'default.hbs'),
      '<h1>{{title}}</h1><div>{{{body}}}</div>'
    );
    const page = makePage({
      title: 'A & B <tag>',
      html: '<b>raw <em>html</em></b>',
    });

    const html = await renderPageTemplate(page, templateDir);
    expect(html).toContain('<h1>A &amp; B &lt;tag&gt;</h1>');
    expect(html).toContain('<b>raw <em>html</em></b>');
  });

  it('exposes the page data (date, tags, slug) to the template', async () => {
    const root = await makeTempDir();
    const templateDir = path.join(root, 'templates');
    await write(
      path.join(templateDir, 'default.hbs'),
      '<p>{{slug}} / {{date}}</p>{{#each tags}}<span>{{this}}</span>{{/each}}'
    );
    const page = makePage({ date: '2024-05-01', slug: 'a/b' });

    const html = await renderPageTemplate(page, templateDir);
    expect(html).toContain('<p>a/b / 2024-05-01</p>');
    expect(html).toContain('<span>intro</span>');
    expect(html).toContain('<span>demo</span>');
  });
});

describe('renderLayout', () => {
  it('injects page content into the {{{body}}} placeholder', async () => {
    const root = await makeTempDir();
    const templateDir = path.join(root, 'templates');
    await write(
      path.join(templateDir, 'layouts', 'default.hbs'),
      '<html><body><header>{{title}}</header><main>{{{body}}}</main></body></html>'
    );

    const html = await renderLayout('<p>page output</p>', makePage(), templateDir);
    expect(html).toBe(
      '<html><body><header>Hello World</header><main><p>page output</p></main></body></html>'
    );
  });

  it('uses the layout named in the frontmatter', async () => {
    const root = await makeTempDir();
    const templateDir = path.join(root, 'templates');
    await write(
      path.join(templateDir, 'layouts', 'wide.hbs'),
      '<div class="wide">{{{body}}}</div>'
    );
    const page = makePage({ layout: 'wide' });

    const html = await renderLayout('<p>wide page</p>', page, templateDir);
    expect(html).toBe('<div class="wide"><p>wide page</p></div>');
  });

  it('renders the built-in default layout when no layout file exists', async () => {
    const root = await makeTempDir();
    const templateDir = path.join(root, 'templates');
    await write(path.join(templateDir, 'default.hbs'), 'page template only');

    const html = await renderLayout('<p>content</p>', makePage(), templateDir);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Hello World</title>');
    expect(html).toContain('href="index.html"');
    expect(html).toContain('<p>content</p>');
  });
});

describe('renderPageWithTemplates', () => {
  it('renders page template inside a layout that uses partials', async () => {
    const root = await makeTempDir();
    const templateDir = path.join(root, 'templates');
    await write(
      path.join(templateDir, 'default.hbs'),
      '<h1>{{title}}</h1><div class="content">{{{body}}}</div>'
    );
    await write(
      path.join(templateDir, 'layouts', 'default.hbs'),
      '<!DOCTYPE html><html><body>{{> nav}}<main>{{{body}}}</main>{{> footer}}</body></html>'
    );
    await write(path.join(templateDir, 'partials', 'nav.hbs'), '<nav>Home</nav>');
    await write(
      path.join(templateDir, 'partials', 'footer.hbs'),
      '<footer>Bye</footer>'
    );

    await registerPartials(templateDir);
    const html = await renderPageWithTemplates(makePage(), templateDir);

    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<nav>Home</nav>');
    expect(html).toContain('<h1>Hello World</h1>');
    expect(html).toContain('<strong>world</strong>');
    expect(html).toContain('<footer>Bye</footer>');
  });
});

describe('parseFrontmatter', () => {
  it('extracts template and layout from frontmatter', () => {
    const result = parseFrontmatter(`---
title: Blog Post
template: blog
layout: wide
---
Body
`);
    expect(result.template).toBe('blog');
    expect(result.layout).toBe('wide');
  });

  it('leaves template and layout undefined when absent', () => {
    const result = parseFrontmatter('---\ntitle: Plain\n---\nBody');
    expect(result.template).toBeUndefined();
    expect(result.layout).toBeUndefined();
  });
});

describe('buildSite with templates', () => {
  it('renders each page with its template and layout', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templateDir = path.join(root, 'templates');

    await write(
      path.join(contentDir, 'blog.md'),
      `---
title: First Post
template: blog
layout: wide
tags: [blog]
---
# First Post
Body **text** here.
`
    );
    await write(
      path.join(contentDir, 'plain.md'),
      `---
title: Plain Page
---
Plain body.
`
    );
    await write(
      path.join(templateDir, 'blog.hbs'),
      '<article class="blog-post"><h1>{{title}}</h1>{{{body}}}</article>'
    );
    await write(
      path.join(templateDir, 'default.hbs'),
      '<main class="page"><h1>{{title}}</h1>{{{body}}}</main>'
    );
    await write(
      path.join(templateDir, 'layouts', 'default.hbs'),
      '<html><body>{{> header}}<div class="shell">{{{body}}}</div>{{> footer}}</body></html>'
    );
    await write(
      path.join(templateDir, 'layouts', 'wide.hbs'),
      '<html><body><div class="wide">{{{body}}}</div></body></html>'
    );
    await write(
      path.join(templateDir, 'partials', 'header.hbs'),
      '<header>Global header</header>'
    );
    await write(
      path.join(templateDir, 'partials', 'footer.hbs'),
      '<footer>Global footer</footer>'
    );

    await buildSite({ contentDir, outputDir, templateDir });

    const blog = await fs.readFile(path.join(outputDir, 'blog.html'), 'utf-8');
    expect(blog).toContain('<div class="wide">');
    expect(blog).toContain('<article class="blog-post">');
    expect(blog).toContain('<h1>First Post</h1>');
    expect(blog).toContain('<strong>text</strong>');

    const plain = await fs.readFile(path.join(outputDir, 'plain.html'), 'utf-8');
    expect(plain).toContain('<div class="shell">');
    expect(plain).toContain('<header>Global header</header>');
    expect(plain).toContain('<main class="page">');
    expect(plain).toContain('<footer>Global footer</footer>');
    expect(plain).toContain('Plain body.');

    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf-8');
    expect(index).toContain('href="blog.html"');
    expect(index).toContain('href="plain.html"');
  });

  it('keeps the legacy hardcoded rendering when no template dir exists', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templateDir = path.join(root, 'does-not-exist');

    await write(
      path.join(contentDir, 'legacy.md'),
      `---
title: Legacy Page
tags: [old]
---
# Legacy
Hello **legacy**.
`
    );

    await buildSite({ contentDir, outputDir, templateDir });

    const html = await fs.readFile(path.join(outputDir, 'legacy.html'), 'utf-8');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Legacy Page</title>');
    expect(html).toContain('<h1>Legacy Page</h1>');
    expect(html).toContain('class="tag">old');
    expect(html).toContain('<strong>legacy</strong>');
    expect(html).toContain('href="index.html"');
  });
});
