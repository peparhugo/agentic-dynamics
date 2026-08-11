import { generateSite } from '../src/generator';
import { Page } from '../src/types';
import fs from 'fs';
import path from 'path';
import os from 'os';

describe('generateSite', () => {
  let outputDir: string;

  beforeEach(() => {
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
  });

  afterEach(() => {
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  const pages: Page[] = [
    {
      frontmatter: {
        title: 'Post One',
        date: '2024-03-01',
        tags: ['tag1', 'tag2'],
      },
      html: '<p>Content one</p>',
      slug: 'post-one',
    },
    {
      frontmatter: { title: 'Post Two', date: '2024-01-15', tags: [] },
      html: '<p>Content two</p>',
      slug: 'post-two',
    },
  ];

  it('creates individual page HTML files (fallback)', () => {
    generateSite(pages, outputDir);

    const postOnePath = path.join(outputDir, 'post-one.html');
    const postTwoPath = path.join(outputDir, 'post-two.html');

    expect(fs.existsSync(postOnePath)).toBe(true);
    expect(fs.existsSync(postTwoPath)).toBe(true);

    const contentOne = fs.readFileSync(postOnePath, 'utf-8');
    expect(contentOne).toContain('Post One');
    expect(contentOne).toContain('Content one');
    expect(contentOne).toContain('2024-03-01');
    expect(contentOne).toContain('tag1');
    expect(contentOne).toContain('tag2');
  });

  it('creates index.html listing all pages (fallback)', () => {
    generateSite(pages, outputDir);

    const indexPath = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const content = fs.readFileSync(indexPath, 'utf-8');
    expect(content).toContain('All Posts');
    expect(content).toContain('Post One');
    expect(content).toContain('Post Two');
    expect(content).toContain('post-one.html');
    expect(content).toContain('post-two.html');
  });

  it('handles empty pages array (fallback)', () => {
    generateSite([], outputDir);

    const indexPath = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const content = fs.readFileSync(indexPath, 'utf-8');
    expect(content).toContain('All Posts');
  });

  it('uses template engine when template directory is provided', () => {
    const templateDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));

    fs.mkdirSync(path.join(templateDir, 'layouts'));
    fs.mkdirSync(path.join(templateDir, 'partials'));

    fs.writeFileSync(
      path.join(templateDir, 'layouts', 'default.hbs'),
      '<!DOCTYPE html><html><head><title>{{title}}</title></head><body><nav>{{> nav}}</nav>{{{body}}}</body></html>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'page.hbs'),
      '<article><h1>{{title}}</h1>{{#if date}}<time>{{date}}</time>{{/if}}{{{content}}}</article>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'index.hbs'),
      '<h1>Posts</h1><ul>{{#each pages}}<li><a href="{{slug}}.html">{{title}}</a></li>{{/each}}</ul>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'partials', 'nav.hbs'),
      '<a href="index.html">Home</a>'
    );

    generateSite(pages, outputDir, templateDir);

    const postOneContent = fs.readFileSync(
      path.join(outputDir, 'post-one.html'),
      'utf-8'
    );
    expect(postOneContent).toContain('Post One');
    expect(postOneContent).toContain('<article>');
    expect(postOneContent).toContain('<time>2024-03-01</time>');
    expect(postOneContent).toContain('<a href="index.html">Home</a>');

    const postTwoContent = fs.readFileSync(
      path.join(outputDir, 'post-two.html'),
      'utf-8'
    );
    expect(postTwoContent).toContain('Post Two');
    expect(postTwoContent).toContain('<time>2024-01-15</time>');

    const indexContent = fs.readFileSync(
      path.join(outputDir, 'index.html'),
      'utf-8'
    );
    expect(indexContent).toContain('Posts');
    expect(indexContent).toContain('post-one.html');
    expect(indexContent).toContain('post-two.html');

    fs.rmSync(templateDir, { recursive: true, force: true });
  });

  it('uses custom template and layout from frontmatter', () => {
    const templateDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));

    fs.mkdirSync(path.join(templateDir, 'layouts'));
    fs.mkdirSync(path.join(templateDir, 'partials'));

    fs.writeFileSync(
      path.join(templateDir, 'layouts', 'default.hbs'),
      '<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'layouts', 'post.hbs'),
      '<html><head><title>Blog: {{title}}</title></head><body>{{{body}}}</body></html>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'page.hbs'),
      '<p>default page</p>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'custom.hbs'),
      '<article class="custom"><h1>{{title}}</h1>{{{content}}}</article>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'index.hbs'),
      '<h1>Index</h1>'
    );

    const customPages: Page[] = [
      {
        frontmatter: {
          title: 'Custom Post',
          date: '2024-05-01',
          tags: [],
          template: 'custom',
          layout: 'post',
        },
        html: '<p>Custom content</p>',
        slug: 'custom-post',
      },
    ];

    generateSite(customPages, outputDir, templateDir);

    const content = fs.readFileSync(
      path.join(outputDir, 'custom-post.html'),
      'utf-8'
    );
    expect(content).toContain('Blog: Custom Post');
    expect(content).toContain('<article class="custom">');
    expect(content).toContain('Custom content');

    fs.rmSync(templateDir, { recursive: true, force: true });
  });

  it('falls back to default template when specified template not found', () => {
    const templateDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));

    fs.mkdirSync(path.join(templateDir, 'layouts'));
    fs.writeFileSync(
      path.join(templateDir, 'layouts', 'default.hbs'),
      '<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'page.hbs'),
      '<article><h1>{{title}}</h1>{{{content}}}</article>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'index.hbs'),
      '<h1>Index</h1>'
    );

    const pagesWithMissingTemplate: Page[] = [
      {
        frontmatter: {
          title: 'Fallback Post',
          date: '',
          tags: [],
          template: 'nonexistent',
        },
        html: '<p>Fallback content</p>',
        slug: 'fallback-post',
      },
    ];

    generateSite(pagesWithMissingTemplate, outputDir, templateDir);

    const content = fs.readFileSync(
      path.join(outputDir, 'fallback-post.html'),
      'utf-8'
    );
    expect(content).toContain('Fallback Post');
    expect(content).toContain('<article>');
    expect(content).toContain('Fallback content');

    fs.rmSync(templateDir, { recursive: true, force: true });
  });

  it('includes partials in rendered output', () => {
    const templateDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));

    fs.mkdirSync(path.join(templateDir, 'layouts'));
    fs.mkdirSync(path.join(templateDir, 'partials'));

    fs.writeFileSync(
      path.join(templateDir, 'layouts', 'default.hbs'),
      '<html><head><title>{{title}}</title></head><body>{{> header}}{{> nav}}{{{body}}}{{> footer}}</body></html>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'page.hbs'),
      '<article><h1>{{title}}</h1>{{{content}}}</article>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'index.hbs'),
      '<h1>Index</h1>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'partials', 'header.hbs'),
      '<header>Site Header</header>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'partials', 'nav.hbs'),
      '<nav>Navigation</nav>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'partials', 'footer.hbs'),
      '<footer>Site Footer</footer>'
    );

    const testPages: Page[] = [
      {
        frontmatter: { title: 'Partial Post', date: '', tags: [] },
        html: '<p>Partial content</p>',
        slug: 'partial-post',
      },
    ];

    generateSite(testPages, outputDir, templateDir);

    const content = fs.readFileSync(
      path.join(outputDir, 'partial-post.html'),
      'utf-8'
    );
    expect(content).toContain('<header>Site Header</header>');
    expect(content).toContain('<nav>Navigation</nav>');
    expect(content).toContain('<footer>Site Footer</footer>');
    expect(content).toContain('Partial content');

    fs.rmSync(templateDir, { recursive: true, force: true });
  });

  it('uses raw HTML in template via triple braces', () => {
    const templateDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tpl-'));

    fs.mkdirSync(path.join(templateDir, 'layouts'));
    fs.writeFileSync(
      path.join(templateDir, 'layouts', 'default.hbs'),
      '<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'page.hbs'),
      '<article>{{{content}}}</article>'
    );
    fs.writeFileSync(
      path.join(templateDir, 'index.hbs'),
      '<h1>Index</h1>'
    );

    const testPages: Page[] = [
      {
        frontmatter: { title: 'HTML Post', date: '', tags: [] },
        html: '<p>Paragraph <strong>bold</strong></p>',
        slug: 'html-post',
      },
    ];

    generateSite(testPages, outputDir, templateDir);

    const content = fs.readFileSync(
      path.join(outputDir, 'html-post.html'),
      'utf-8'
    );
    expect(content).toContain('<p>Paragraph <strong>bold</strong></p>');

    fs.rmSync(templateDir, { recursive: true, force: true });
  });
});
