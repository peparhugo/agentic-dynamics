import * as fs from 'fs';
import * as path from 'path';
import { build } from '../ssg.js';

describe('Static Site Generator', () => {
  let testContentDir: string;
  let testOutputDir: string;

  beforeEach(() => {
    testContentDir = path.join('/tmp', `test-content-${Date.now()}`);
    testOutputDir = path.join('/tmp', `test-output-${Date.now()}`);
    fs.mkdirSync(testContentDir, { recursive: true });
  });

  afterEach(() => {
    if (fs.existsSync(testContentDir)) {
      fs.rmSync(testContentDir, { recursive: true });
    }
    if (fs.existsSync(testOutputDir)) {
      fs.rmSync(testOutputDir, { recursive: true });
    }
  });

  it('should create output directory if it does not exist', async () => {
    fs.writeFileSync(path.join(testContentDir, 'test.md'), '# Test\nContent');
    await build(testContentDir, testOutputDir);
    expect(fs.existsSync(testOutputDir)).toBe(true);
  });

  it('should generate index.html when no markdown files exist', async () => {
    await build(testContentDir, testOutputDir);
    const indexPath = path.join(testOutputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);
    const content = fs.readFileSync(indexPath, 'utf-8');
    expect(content).toContain('No pages found');
  });

  it('should parse markdown and create HTML files', async () => {
    const mdContent = `---
title: Test Post
---
# Test Post
This is test content.`;

    fs.writeFileSync(path.join(testContentDir, 'test.md'), mdContent);
    await build(testContentDir, testOutputDir);

    const htmlPath = path.join(testOutputDir, 'test.html');
    expect(fs.existsSync(htmlPath)).toBe(true);

    const html = fs.readFileSync(htmlPath, 'utf-8');
    expect(html).toContain('Test Post');
    expect(html).toContain('This is test content');
  });

  it('should generate index.html with links to all pages', () => {
    const post1 = `---
title: First Post
---
Content 1`;

    const post2 = `---
title: Second Post
date: 2024-01-15
---
Content 2`;

    fs.writeFileSync(path.join(testContentDir, 'first.md'), post1);
    fs.writeFileSync(path.join(testContentDir, 'second.md'), post2);
    build(testContentDir, testOutputDir);

    const indexPath = path.join(testOutputDir, 'index.html');
    const index = fs.readFileSync(indexPath, 'utf-8');

    expect(index).toContain('first.html');
    expect(index).toContain('second.html');
    expect(index).toContain('First Post');
    expect(index).toContain('Second Post');
    expect(index).toContain('2024-01-15');
  });

  it('should include back link in page HTML', () => {
    const mdContent = `---
title: Test
---
Content`;

    fs.writeFileSync(path.join(testContentDir, 'test.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'test.html'), 'utf-8');
    expect(html).toContain('← Home');
    expect(html).toContain('/index.html');
  });

  it('should handle markdown with code blocks', () => {
    const mdContent = `---
title: Code Post
---
\`\`\`javascript
console.log('hello');
\`\`\``;

    fs.writeFileSync(path.join(testContentDir, 'code.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'code.html'), 'utf-8');
    expect(html).toContain('console.log');
  });

  it('should handle markdown with lists', () => {
    const mdContent = `---
title: Lists
---
- Item 1
- Item 2
- Item 3`;

    fs.writeFileSync(path.join(testContentDir, 'lists.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'lists.html'), 'utf-8');
    expect(html).toContain('Item 1');
    expect(html).toContain('Item 2');
    expect(html).toContain('Item 3');
  });

  it('should include date in page HTML if present', () => {
    const mdContent = `---
title: Dated Post
date: 2024-01-15
---
Content`;

    fs.writeFileSync(path.join(testContentDir, 'dated.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'dated.html'), 'utf-8');
    expect(html).toContain('2024-01-15');
    expect(html).toContain('class="date"');
  });

  it('should include tags in page HTML if present', () => {
    const mdContent = `---
title: Tagged Post
tags: [javascript, typescript, web]
---
Content`;

    fs.writeFileSync(path.join(testContentDir, 'tagged.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'tagged.html'), 'utf-8');
    expect(html).toContain('javascript');
    expect(html).toContain('typescript');
    expect(html).toContain('web');
    expect(html).toContain('class="tags"');
  });

  it('should generate proper HTML structure with charset and viewport', () => {
    const mdContent = `---
title: Test
---
Content`;

    fs.writeFileSync(path.join(testContentDir, 'test.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'test.html'), 'utf-8');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('charset="UTF-8"');
    expect(html).toContain('viewport');
  });

  it('should slugify filenames correctly', () => {
    const mdContent = `---
title: Test
---
Content`;

    fs.writeFileSync(path.join(testContentDir, 'My Test Page.md'), mdContent);
    build(testContentDir, testOutputDir);

    const htmlPath = path.join(testOutputDir, 'my-test-page.html');
    expect(fs.existsSync(htmlPath)).toBe(true);
  });

  it('should handle multiple markdown files in sequence', () => {
    for (let i = 1; i <= 3; i++) {
      const mdContent = `---
title: Post ${i}
date: 2024-01-${String(i).padStart(2, '0')}
---
Content for post ${i}`;

      fs.writeFileSync(path.join(testContentDir, `post${i}.md`), mdContent);
    }

    build(testContentDir, testOutputDir);

    for (let i = 1; i <= 3; i++) {
      const htmlPath = path.join(testOutputDir, `post${i}.html`);
      expect(fs.existsSync(htmlPath)).toBe(true);
    }

    const indexPath = path.join(testOutputDir, 'index.html');
    const index = fs.readFileSync(indexPath, 'utf-8');
    expect(index).toContain('Post 1');
    expect(index).toContain('Post 2');
    expect(index).toContain('Post 3');
  });

  it('should handle content directory that does not exist', () => {
    const nonExistentDir = path.join('/tmp', `non-existent-${Date.now()}`);
    expect(() => build(nonExistentDir, testOutputDir)).not.toThrow();
    expect(fs.existsSync(testOutputDir)).toBe(true);
  });

  it('should use filename as title if not provided in frontmatter', () => {
    const mdContent = `---
---
Content without title`;

    fs.writeFileSync(path.join(testContentDir, 'my-page.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'my-page.html'), 'utf-8');
    expect(html).toContain('my-page');
  });

  it('should render markdown links correctly', () => {
    const mdContent = `---
title: Links
---
[Link text](https://example.com)`;

    fs.writeFileSync(path.join(testContentDir, 'links.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'links.html'), 'utf-8');
    expect(html).toContain('https://example.com');
    expect(html).toContain('Link text');
  });

  it('should render markdown emphasis correctly', () => {
    const mdContent = `---
title: Emphasis
---
**bold** and *italic* and ***bold italic***`;

    fs.writeFileSync(path.join(testContentDir, 'emphasis.md'), mdContent);
    build(testContentDir, testOutputDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'emphasis.html'), 'utf-8');
    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('<em>italic</em>');
  });

  it('should use custom template from frontmatter', () => {
    const templatesDir = path.join('/tmp', `test-templates-${Date.now()}`);
    fs.mkdirSync(templatesDir, { recursive: true });

    const customTemplate = `<section>
<h2>{{title}}</h2>
{{{body}}}
</section>`;

    fs.writeFileSync(path.join(templatesDir, 'custom.hbs'), customTemplate);

    const mdContent = `---
title: Custom Template
template: custom
---
Custom content here`;

    fs.writeFileSync(path.join(testContentDir, 'custom.md'), mdContent);
    build(testContentDir, testOutputDir, templatesDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'custom.html'), 'utf-8');
    expect(html).toContain('<section>');
    expect(html).toContain('<h2>Custom Template</h2>');
    expect(html).toContain('Custom content here');

    if (fs.existsSync(templatesDir)) {
      fs.rmSync(templatesDir, { recursive: true });
    }
  });

  it('should use custom layout from frontmatter', () => {
    const templatesDir = path.join('/tmp', `test-templates-${Date.now()}`);
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });

    const customLayout = `<!DOCTYPE html>
<html>
<head><title>{{title}}</title></head>
<body>
<div class="wrapper">
{{{body}}}
</div>
</body>
</html>`;

    fs.writeFileSync(path.join(layoutsDir, 'custom.hbs'), customLayout);

    const mdContent = `---
title: Custom Layout
layout: custom
---
Content in custom layout`;

    fs.writeFileSync(path.join(testContentDir, 'layout-test.md'), mdContent);
    build(testContentDir, testOutputDir, templatesDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'layout-test.html'), 'utf-8');
    expect(html).toContain('<div class="wrapper">');
    expect(html).toContain('Content in custom layout');

    if (fs.existsSync(templatesDir)) {
      fs.rmSync(templatesDir, { recursive: true });
    }
  });

  it('should use both custom template and layout', () => {
    const templatesDir = path.join('/tmp', `test-templates-${Date.now()}`);
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });

    const customTemplate = `<article class="post">
<h1>{{title}}</h1>
{{{body}}}
</article>`;

    const customLayout = `<!DOCTYPE html>
<html>
<body class="page">
{{{body}}}
</body>
</html>`;

    fs.writeFileSync(path.join(templatesDir, 'blog.hbs'), customTemplate);
    fs.writeFileSync(path.join(layoutsDir, 'blog.hbs'), customLayout);

    const mdContent = `---
title: Blog Post
template: blog
layout: blog
---
Post content here`;

    fs.writeFileSync(path.join(testContentDir, 'blog.md'), mdContent);
    build(testContentDir, testOutputDir, templatesDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'blog.html'), 'utf-8');
    expect(html).toContain('<body class="page">');
    expect(html).toContain('<article class="post">');
    expect(html).toContain('<h1>Blog Post</h1>');
    expect(html).toContain('Post content here');

    if (fs.existsSync(templatesDir)) {
      fs.rmSync(templatesDir, { recursive: true });
    }
  });

  it('should create template directories if they do not exist', () => {
    const templatesDir = path.join('/tmp', `test-templates-${Date.now()}`);

    const mdContent = `---
title: Test
---
Content`;

    fs.writeFileSync(path.join(testContentDir, 'test.md'), mdContent);
    build(testContentDir, testOutputDir, templatesDir);

    expect(fs.existsSync(templatesDir)).toBe(true);
    expect(fs.existsSync(path.join(templatesDir, 'layouts'))).toBe(true);
    expect(fs.existsSync(path.join(templatesDir, 'partials'))).toBe(true);

    if (fs.existsSync(templatesDir)) {
      fs.rmSync(templatesDir, { recursive: true });
    }
  });

  it('should register partials from partials directory', () => {
    const templatesDir = path.join('/tmp', `test-templates-${Date.now()}`);
    const partialsDir = path.join(templatesDir, 'partials');
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(partialsDir, { recursive: true });
    fs.mkdirSync(layoutsDir, { recursive: true });

    const headerPartial = `<header><h1>My Site</h1></header>`;
    const footerPartial = `<footer>© 2024</footer>`;

    fs.writeFileSync(path.join(partialsDir, 'header.hbs'), headerPartial);
    fs.writeFileSync(path.join(partialsDir, 'footer.hbs'), footerPartial);

    const customLayout = `<!DOCTYPE html>
<html>
<body>
{{>header}}
<main>
{{{body}}}
</main>
{{>footer}}
</body>
</html>`;

    fs.writeFileSync(path.join(layoutsDir, 'with-partials.hbs'), customLayout);

    const mdContent = `---
title: With Partials
layout: with-partials
---
Main content`;

    fs.writeFileSync(path.join(testContentDir, 'partials-test.md'), mdContent);
    build(testContentDir, testOutputDir, templatesDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'partials-test.html'), 'utf-8');
    expect(html).toContain('<header><h1>My Site</h1></header>');
    expect(html).toContain('<footer>© 2024</footer>');
    expect(html).toContain('Main content');

    if (fs.existsSync(templatesDir)) {
      fs.rmSync(templatesDir, { recursive: true });
    }
  });

  it('should fallback to default template when custom not found', () => {
    const templatesDir = path.join('/tmp', `test-templates-${Date.now()}`);
    fs.mkdirSync(templatesDir, { recursive: true });

    const mdContent = `---
title: Fallback Test
template: nonexistent
---
Content`;

    fs.writeFileSync(path.join(testContentDir, 'fallback.md'), mdContent);
    build(testContentDir, testOutputDir, templatesDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'fallback.html'), 'utf-8');
    expect(html).toContain('Fallback Test');
    expect(html).toContain('Content');
    expect(html).toContain('<!DOCTYPE html>');

    if (fs.existsSync(templatesDir)) {
      fs.rmSync(templatesDir, { recursive: true });
    }
  });

  it('should render default template with metadata variables', () => {
    const templatesDir = path.join('/tmp', `test-templates-${Date.now()}`);
    fs.mkdirSync(templatesDir, { recursive: true });

    const mdContent = `---
title: With Metadata
date: 2024-08-15
tags: [template, test]
---
Content`;

    fs.writeFileSync(path.join(testContentDir, 'metadata.md'), mdContent);
    build(testContentDir, testOutputDir, templatesDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'metadata.html'), 'utf-8');
    expect(html).toContain('With Metadata');
    expect(html).toContain('2024-08-15');
    expect(html).toContain('template');
    expect(html).toContain('test');

    if (fs.existsSync(templatesDir)) {
      fs.rmSync(templatesDir, { recursive: true });
    }
  });

  it('should use index template if specified', () => {
    const templatesDir = path.join('/tmp', `test-templates-${Date.now()}`);
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });

    const customIndexLayout = `<!DOCTYPE html>
<html>
<head><title>All Posts</title></head>
<body>
<div class="posts">
{{#each pages}}<div class="post-link"><a href="{{this.slug}}.html">{{this.title}}</a></div>
{{/each}}
</div>
</body>
</html>`;

    fs.writeFileSync(path.join(layoutsDir, 'index.hbs'), customIndexLayout);

    const post1 = `---
title: First Post
---
Content 1`;

    const post2 = `---
title: Second Post
---
Content 2`;

    fs.writeFileSync(path.join(testContentDir, 'first.md'), post1);
    fs.writeFileSync(path.join(testContentDir, 'second.md'), post2);
    build(testContentDir, testOutputDir, templatesDir);

    const indexHtml = fs.readFileSync(path.join(testOutputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('<div class="posts">');
    expect(indexHtml).toContain('<div class="post-link">');
    expect(indexHtml).toContain('All Posts');

    if (fs.existsSync(templatesDir)) {
      fs.rmSync(templatesDir, { recursive: true });
    }
  });

  it('should support templates with conditional blocks', () => {
    const templatesDir = path.join('/tmp', `test-templates-${Date.now()}`);
    fs.mkdirSync(templatesDir, { recursive: true });

    const conditionalTemplate = `<article>
<h1>{{title}}</h1>
{{#if date}}<time>{{date}}</time>{{/if}}
{{{body}}}
</article>`;

    fs.writeFileSync(path.join(templatesDir, 'conditional.hbs'), conditionalTemplate);

    const mdWithDate = `---
title: With Date
date: 2024-08-15
template: conditional
---
Content with date`;

    const mdWithoutDate = `---
title: No Date
template: conditional
---
Content without date`;

    fs.writeFileSync(path.join(testContentDir, 'with-date.md'), mdWithDate);
    fs.writeFileSync(path.join(testContentDir, 'no-date.md'), mdWithoutDate);
    build(testContentDir, testOutputDir, templatesDir);

    const htmlWithDate = fs.readFileSync(path.join(testOutputDir, 'with-date.html'), 'utf-8');
    expect(htmlWithDate).toContain('<time>2024-08-15</time>');

    const htmlWithoutDate = fs.readFileSync(path.join(testOutputDir, 'no-date.html'), 'utf-8');
    expect(htmlWithoutDate).not.toContain('<time>');

    if (fs.existsSync(templatesDir)) {
      fs.rmSync(templatesDir, { recursive: true });
    }
  });

  it('should support templates with loops for tags', () => {
    const templatesDir = path.join('/tmp', `test-templates-${Date.now()}`);
    fs.mkdirSync(templatesDir, { recursive: true });

    const loopTemplate = `<article>
<h1>{{title}}</h1>
{{#if tags}}<div class="tags">
{{#each tags}}<span class="tag">{{this}}</span>
{{/each}}</div>{{/if}}
{{{body}}}
</article>`;

    fs.writeFileSync(path.join(templatesDir, 'with-tags.hbs'), loopTemplate);

    const mdContent = `---
title: Tagged Post
tags: [javascript, typescript, web]
template: with-tags
---
Post content`;

    fs.writeFileSync(path.join(testContentDir, 'tagged-post.md'), mdContent);
    build(testContentDir, testOutputDir, templatesDir);

    const html = fs.readFileSync(path.join(testOutputDir, 'tagged-post.html'), 'utf-8');
    expect(html).toContain('<span class="tag">javascript</span>');
    expect(html).toContain('<span class="tag">typescript</span>');
    expect(html).toContain('<span class="tag">web</span>');

    if (fs.existsSync(templatesDir)) {
      fs.rmSync(templatesDir, { recursive: true });
    }
  });
});
