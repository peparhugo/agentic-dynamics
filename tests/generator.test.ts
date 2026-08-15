import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { SiteGenerator } from '../src/generator';

describe('SiteGenerator', () => {
  let tempDir: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
    contentDir = path.join(tempDir, 'content');
    outputDir = path.join(tempDir, 'dist');
    fs.mkdirSync(contentDir);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('should generate HTML files from markdown', async () => {
    const markdownContent = `---
title: Test Post
date: 2024-01-15
tags: test, markdown
---

# Test Post

This is a test post.`;

    fs.writeFileSync(path.join(contentDir, 'test.md'), markdownContent);

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const outputFile = path.join(outputDir, 'test.html');
    expect(fs.existsSync(outputFile)).toBe(true);

    const content = fs.readFileSync(outputFile, 'utf-8');
    expect(content).toContain('<title>Test Post</title>');
    expect(content).toContain('<h1>Test Post</h1>');
    expect(content).toContain('This is a test post.');
  });

  it('should generate index.html with all pages', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'first.md'),
      `---
title: First Page
date: 2024-01-01
---

Content of first page.`
    );

    fs.writeFileSync(
      path.join(contentDir, 'second.md'),
      `---
title: Second Page
date: 2024-01-02
tags: important
---

Content of second page.`
    );

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const indexFile = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexFile)).toBe(true);

    const indexContent = fs.readFileSync(indexFile, 'utf-8');
    expect(indexContent).toContain('First Page');
    expect(indexContent).toContain('Second Page');
    expect(indexContent).toContain('first.html');
    expect(indexContent).toContain('second.html');
    expect(indexContent).toContain('2024-01-01');
    expect(indexContent).toContain('2024-01-02');
    expect(indexContent).toContain('important');
  });

  it('should handle markdown without frontmatter', async () => {
    const markdownContent = `# No Frontmatter

Just plain markdown.`;

    fs.writeFileSync(path.join(contentDir, 'plain.md'), markdownContent);

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const outputFile = path.join(outputDir, 'plain.html');
    expect(fs.existsSync(outputFile)).toBe(true);

    const content = fs.readFileSync(outputFile, 'utf-8');
    expect(content).toContain('<title>plain</title>');
  });

  it('should create output directory if it does not exist', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'test.md'),
      `---
title: Test
---

Content.`
    );

    expect(fs.existsSync(outputDir)).toBe(false);

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    expect(fs.existsSync(outputDir)).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'test.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
  });

  it('should handle empty content directory', async () => {
    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    expect(fs.existsSync(outputDir)).toBe(true);

    const indexFile = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexFile)).toBe(true);

    const indexContent = fs.readFileSync(indexFile, 'utf-8');
    expect(indexContent).toContain('No pages found');
  });

  it('should only process .md files', async () => {
    fs.writeFileSync(path.join(contentDir, 'markdown.md'), '# Markdown\n\nContent.');
    fs.writeFileSync(path.join(contentDir, 'text.txt'), 'This should not be processed.');
    fs.writeFileSync(path.join(contentDir, 'code.js'), 'console.log("ignored");');

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    expect(fs.existsSync(path.join(outputDir, 'markdown.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'text.html'))).toBe(false);
    expect(fs.existsSync(path.join(outputDir, 'code.html'))).toBe(false);
  });

  it('should sort markdown files alphabetically', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'zebra.md'),
      '---\ntitle: Zebra\n---\nZ'
    );
    fs.writeFileSync(
      path.join(contentDir, 'apple.md'),
      '---\ntitle: Apple\n---\nA'
    );
    fs.writeFileSync(
      path.join(contentDir, 'banana.md'),
      '---\ntitle: Banana\n---\nB'
    );

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const indexContent = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    const applePos = indexContent.indexOf('Apple');
    const bananaPos = indexContent.indexOf('Banana');
    const zebraPos = indexContent.indexOf('Zebra');

    expect(applePos).toBeLessThan(bananaPos);
    expect(bananaPos).toBeLessThan(zebraPos);
  });

  it('should escape HTML in titles', async () => {
    const markdownContent = `---
title: <script>alert('xss')</script>
---

Normal content.`;

    fs.writeFileSync(path.join(contentDir, 'xss.md'), markdownContent);

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const content = fs.readFileSync(path.join(outputDir, 'xss.html'), 'utf-8');
    expect(content).toContain('&lt;script&gt;');
    expect(content).toContain('&lt;/script&gt;');
    expect(content).not.toContain('<title><script>');
  });

  it('should include navigation link to index from page', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'page.md'),
      '---\ntitle: Page\n---\nContent.'
    );

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const content = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(content).toContain('index.html');
    expect(content).toContain('← Home');
  });

  it('should display tags in index', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'tagged.md'),
      '---\ntitle: Tagged Post\ntags: typescript, testing, cli\n---\nContent.'
    );

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const indexContent = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexContent).toContain('typescript');
    expect(indexContent).toContain('testing');
    expect(indexContent).toContain('cli');
  });

  it('should use custom templates when template directory exists', async () => {
    const templatesDir = path.join(tempDir, 'templates');
    fs.mkdirSync(templatesDir);
    fs.mkdirSync(path.join(templatesDir, 'layouts'));

    const pageTemplate = '<div class="page">{{content}}</div>';
    const layoutTemplate = '<html><body>{{{body}}}</body></html>';

    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), pageTemplate);
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), layoutTemplate);

    fs.writeFileSync(
      path.join(contentDir, 'test.md'),
      '---\ntitle: Test Page\ntemplate: page\nlayout: default\n---\n\n# Content'
    );

    const generator = new SiteGenerator({
      contentDir,
      outputDir,
      templatesDir,
    });
    await generator.build();

    const content = fs.readFileSync(path.join(outputDir, 'test.html'), 'utf-8');
    expect(content).toContain('<html>');
    expect(content).toContain('<body>');
    expect(content).toContain('class="page"');
  });

  it('should fall back to default HTML if template is missing', async () => {
    const templatesDir = path.join(tempDir, 'templates');
    fs.mkdirSync(templatesDir);
    fs.mkdirSync(path.join(templatesDir, 'layouts'));

    fs.writeFileSync(path.join(contentDir, 'test.md'), '---\ntitle: Test\ntemplate: page\n---\nContent');

    const generator = new SiteGenerator({
      contentDir,
      outputDir,
      templatesDir,
    });
    await generator.build();

    const content = fs.readFileSync(path.join(outputDir, 'test.html'), 'utf-8');
    expect(content).toContain('<!DOCTYPE html>');
    expect(content).toContain('<title>Test</title>');
  });

  it('should support template frontmatter variable', async () => {
    const templatesDir = path.join(tempDir, 'templates');
    fs.mkdirSync(templatesDir);
    fs.mkdirSync(path.join(templatesDir, 'layouts'));

    const postTemplate = '<article class="post">{{content}}</article>';
    fs.writeFileSync(path.join(templatesDir, 'post.hbs'), postTemplate);
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'blog.hbs'),
      '<div class="blog">{{{body}}}</div>'
    );

    fs.writeFileSync(
      path.join(contentDir, 'article.md'),
      '---\ntitle: My Post\ntemplate: post\nlayout: blog\n---\n\n# Article Content'
    );

    const generator = new SiteGenerator({
      contentDir,
      outputDir,
      templatesDir,
    });
    await generator.build();

    const content = fs.readFileSync(path.join(outputDir, 'article.html'), 'utf-8');
    expect(content).toContain('class="blog"');
    expect(content).toContain('class="post"');
  });

  it('should support partials in templates', async () => {
    const templatesDir = path.join(tempDir, 'templates');
    fs.mkdirSync(templatesDir);
    fs.mkdirSync(path.join(templatesDir, 'layouts'));
    fs.mkdirSync(path.join(templatesDir, 'partials'));

    const headerPartial = '<header>My Site</header>';
    const footerPartial = '<footer>© 2024</footer>';
    fs.writeFileSync(path.join(templatesDir, 'partials', 'header.hbs'), headerPartial);
    fs.writeFileSync(path.join(templatesDir, 'partials', 'footer.hbs'), footerPartial);

    const layoutTemplate = '{{>header}}<main>{{{body}}}</main>{{>footer}}';
    fs.writeFileSync(path.join(templatesDir, 'layouts', 'default.hbs'), layoutTemplate);

    const pageTemplate = '<h1>{{title}}</h1>{{content}}';
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), pageTemplate);

    fs.writeFileSync(
      path.join(contentDir, 'test.md'),
      '---\ntitle: Test\ntemplate: page\nlayout: default\n---\n\nPage content'
    );

    const generator = new SiteGenerator({
      contentDir,
      outputDir,
      templatesDir,
    });
    await generator.build();

    const content = fs.readFileSync(path.join(outputDir, 'test.html'), 'utf-8');
    expect(content).toContain('<header>My Site</header>');
    expect(content).toContain('<footer>© 2024</footer>');
    expect(content).toContain('<h1>Test</h1>');
  });

  it('should work without templates directory', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'simple.md'),
      '---\ntitle: Simple Page\n---\n\nSimple content'
    );

    const generator = new SiteGenerator({
      contentDir,
      outputDir,
    });
    await generator.build();

    const content = fs.readFileSync(path.join(outputDir, 'simple.html'), 'utf-8');
    expect(content).toContain('<!DOCTYPE html>');
    expect(content).toContain('<title>Simple Page</title>');
  });

  it('should preserve backward compatibility without template config', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'page.md'),
      '---\ntitle: Backward Compat\ndate: 2024-01-01\ntags: old, style\n---\n\nOld style page'
    );

    const generator = new SiteGenerator({ contentDir, outputDir });
    await generator.build();

    const content = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(content).toContain('<!DOCTYPE html>');
    expect(content).toContain('<title>Backward Compat</title>');
    expect(content).toContain('← Home');
    expect(content).toContain('Old style page');
  });

  it('should pass custom frontmatter fields to templates', async () => {
    const templatesDir = path.join(tempDir, 'templates');
    fs.mkdirSync(templatesDir);
    fs.mkdirSync(path.join(templatesDir, 'layouts'));

    const pageTemplate = '<h1>{{title}}</h1><p>Author: {{author}}</p>{{content}}';
    fs.writeFileSync(path.join(templatesDir, 'page.hbs'), pageTemplate);
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<article>{{{body}}}</article>'
    );

    fs.writeFileSync(
      path.join(contentDir, 'post.md'),
      '---\ntitle: Custom Post\nauthor: Jane Doe\ntemplate: page\nlayout: default\n---\n\nContent here'
    );

    const generator = new SiteGenerator({
      contentDir,
      outputDir,
      templatesDir,
    });
    await generator.build();

    const content = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
    expect(content).toContain('<h1>Custom Post</h1>');
    expect(content).toContain('<p>Author: Jane Doe</p>');
  });
});
