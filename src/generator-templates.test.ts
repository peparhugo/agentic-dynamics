import fs from 'fs';
import path from 'path';
import {
  generatePageHtmlWithTemplate,
  generatePages,
  parseMarkdownFile,
  build,
} from './generator';
import { TemplateEngine } from './templates';

const TEST_CONTENT_DIR = path.join(__dirname, '__test-content-templates');
const TEST_OUTPUT_DIR = path.join(__dirname, '__test-output-templates');
const TEST_TEMPLATES_DIR = path.join(__dirname, '__test-templates-gen');
const TEST_LAYOUTS_DIR = path.join(TEST_TEMPLATES_DIR, 'layouts');
const TEST_PARTIALS_DIR = path.join(TEST_TEMPLATES_DIR, 'partials');

function setupTestDirs(): void {
  for (const dir of [TEST_CONTENT_DIR, TEST_OUTPUT_DIR, TEST_TEMPLATES_DIR, TEST_LAYOUTS_DIR, TEST_PARTIALS_DIR]) {
    if (fs.existsSync(dir)) {
      fs.rmSync(dir, { recursive: true });
    }
    fs.mkdirSync(dir, { recursive: true });
  }
}

function cleanupTestDirs(): void {
  for (const dir of [TEST_CONTENT_DIR, TEST_OUTPUT_DIR, TEST_TEMPLATES_DIR]) {
    if (fs.existsSync(dir)) {
      fs.rmSync(dir, { recursive: true });
    }
  }
}

describe('Generator with Templates', () => {
  beforeEach(setupTestDirs);
  afterEach(cleanupTestDirs);

  describe('generatePageHtmlWithTemplate', () => {
    it('should render page with template', async () => {
      const pageContent = `---
title: Test Post
date: 2023-01-01
---
# Heading

This is content.`;

      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'test.md'), pageContent);
      const pageData = await parseMarkdownFile(
        path.join(TEST_CONTENT_DIR, 'test.md')
      );

      const templateContent = `
<article>
  <h1>{{title}}</h1>
  <div class="content">{{{content}}}</div>
</article>`;
      fs.writeFileSync(
        path.join(TEST_TEMPLATES_DIR, 'page.hbs'),
        templateContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const html = generatePageHtmlWithTemplate(pageData, engine);

      expect(html).toContain('<h1>Test Post</h1>');
      expect(html).toContain('<h1>Heading</h1>');
      expect(html).toContain('This is content');
    });

    it('should apply layout to rendered template', async () => {
      const pageContent = `---
title: Test Page
---
# Page Heading`;

      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page.md'), pageContent);
      const pageData = await parseMarkdownFile(
        path.join(TEST_CONTENT_DIR, 'page.md')
      );

      const templateContent = `<article>{{{content}}}</article>`;
      fs.writeFileSync(
        path.join(TEST_TEMPLATES_DIR, 'page.hbs'),
        templateContent
      );

      const layoutContent = `<!DOCTYPE html>
<html>
<head><title>{{title}}</title></head>
<body>{{{body}}}</body>
</html>`;
      fs.writeFileSync(
        path.join(TEST_LAYOUTS_DIR, 'default.hbs'),
        layoutContent
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const html = generatePageHtmlWithTemplate(pageData, engine);

      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<title>Test Page</title>');
      expect(html).toContain('<article>');
      expect(html).toContain('<h1>Page Heading</h1>');
    });

    it('should use custom template from frontmatter', async () => {
      const pageContent = `---
title: Blog Post
template: blog
---
# Blog Title`;

      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'post.md'), pageContent);
      const pageData = await parseMarkdownFile(
        path.join(TEST_CONTENT_DIR, 'post.md')
      );

      const blogTemplate = `<div class="blog-post"><h2>{{title}}</h2>{{{content}}}</div>`;
      fs.writeFileSync(
        path.join(TEST_TEMPLATES_DIR, 'blog.hbs'),
        blogTemplate
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const html = generatePageHtmlWithTemplate(pageData, engine);

      expect(html).toContain('class="blog-post"');
      expect(html).toContain('<h2>Blog Post</h2>');
      expect(html).toContain('<h1>Blog Title</h1>');
    });

    it('should use custom layout from frontmatter', async () => {
      const pageContent = `---
title: Special Page
layout: special
---
Content`;

      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'special.md'), pageContent);
      const pageData = await parseMarkdownFile(
        path.join(TEST_CONTENT_DIR, 'special.md')
      );

      const template = `<div>{{{content}}}</div>`;
      fs.writeFileSync(path.join(TEST_TEMPLATES_DIR, 'page.hbs'), template);

      const specialLayout = `<section class="special"><header>{{title}}</header>{{{body}}}</section>`;
      fs.writeFileSync(
        path.join(TEST_LAYOUTS_DIR, 'special.hbs'),
        specialLayout
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const html = generatePageHtmlWithTemplate(pageData, engine);

      expect(html).toContain('class="special"');
      expect(html).toContain('<header>Special Page</header>');
      expect(html).toContain('Content');
    });

    it('should pass all frontmatter to template context', async () => {
      const pageContent = `---
title: Custom Meta
date: 2023-06-15
author: Jane Doe
custom: metadata
---
Content`;

      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'meta.md'), pageContent);
      const pageData = await parseMarkdownFile(
        path.join(TEST_CONTENT_DIR, 'meta.md')
      );

      const template = `<div>Title: {{title}}, Author: {{author}}, Custom: {{custom}}, Date: {{date}}</div>{{{content}}}`;
      fs.writeFileSync(path.join(TEST_TEMPLATES_DIR, 'page.hbs'), template);

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const html = generatePageHtmlWithTemplate(pageData, engine);

      expect(html).toContain('Title: Custom Meta');
      expect(html).toContain('Author: Jane Doe');
      expect(html).toContain('Custom: metadata');
      expect(html).toContain('Date: 2023-06-15');
    });
  });

  describe('generatePages with templates', () => {
    it('should generate pages using templates', async () => {
      const page1 = `---
title: First Page
---
# First Content`;

      const page2 = `---
title: Second Page
---
# Second Content`;

      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page1.md'), page1);
      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page2.md'), page2);

      const template = `<article><h1>{{title}}</h1>{{{content}}}</article>`;
      fs.writeFileSync(path.join(TEST_TEMPLATES_DIR, 'page.hbs'), template);

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const pages = await generatePages(TEST_CONTENT_DIR, TEST_OUTPUT_DIR, engine);

      expect(pages.length).toBe(2);

      const page1Html = fs.readFileSync(
        path.join(TEST_OUTPUT_DIR, 'page1.html'),
        'utf-8'
      );
      expect(page1Html).toContain('<article>');
      expect(page1Html).toContain('<h1>First Page</h1>');
      expect(page1Html).toContain('First Content');

      const page2Html = fs.readFileSync(
        path.join(TEST_OUTPUT_DIR, 'page2.html'),
        'utf-8'
      );
      expect(page2Html).toContain('<h1>Second Page</h1>');
      expect(page2Html).toContain('Second Content');
    });

    it('should generate pages without templates if engine not provided', async () => {
      const content = `---
title: Test
---
Content`;

      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'test.md'), content);

      const pages = await generatePages(TEST_CONTENT_DIR, TEST_OUTPUT_DIR);

      expect(pages.length).toBe(1);
      expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'test.html'))).toBe(true);

      const html = fs.readFileSync(
        path.join(TEST_OUTPUT_DIR, 'test.html'),
        'utf-8'
      );
      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<title>Test</title>');
    });
  });

  describe('build with templates', () => {
    it('should build site with templates when templates dir exists', async () => {
      const content = `---
title: Building Site
date: 2023-08-01
---
# Build Test`;

      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'build.md'), content);

      const template = `<main><h1>{{title}}</h1>{{{content}}}</main>`;
      fs.writeFileSync(path.join(TEST_TEMPLATES_DIR, 'page.hbs'), template);

      const layout = `<!DOCTYPE html><html><body>{{{body}}}</body></html>`;
      fs.writeFileSync(path.join(TEST_LAYOUTS_DIR, 'default.hbs'), layout);

      await build(TEST_CONTENT_DIR, TEST_OUTPUT_DIR, TEST_TEMPLATES_DIR);

      const pageHtml = fs.readFileSync(
        path.join(TEST_OUTPUT_DIR, 'build.html'),
        'utf-8'
      );
      expect(pageHtml).toContain('<!DOCTYPE html>');
      expect(pageHtml).toContain('<main>');
      expect(pageHtml).toContain('<h1>Building Site</h1>');

      const indexHtml = fs.readFileSync(
        path.join(TEST_OUTPUT_DIR, 'index.html'),
        'utf-8'
      );
      expect(indexHtml).toContain('Building Site');
      expect(indexHtml).toContain('build.html');
    });

    it('should build site without templates when templates dir does not exist', async () => {
      const content = `---
title: No Templates
---
Content`;

      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'no-template.md'), content);

      const nonexistentTemplatesDir = path.join(TEST_TEMPLATES_DIR, 'nonexistent');
      await build(TEST_CONTENT_DIR, TEST_OUTPUT_DIR, nonexistentTemplatesDir);

      expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'no-template.html'))).toBe(true);

      const html = fs.readFileSync(
        path.join(TEST_OUTPUT_DIR, 'no-template.html'),
        'utf-8'
      );
      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<title>No Templates</title>');
    });

    it('should use partials in templates during build', async () => {
      const content = `---
title: Page With Partials
---
Content`;

      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'partial-test.md'), content);

      const headerPartial = '<header>My Site</header>';
      const footerPartial = '<footer>© 2023</footer>';
      fs.writeFileSync(
        path.join(TEST_PARTIALS_DIR, 'header.hbs'),
        headerPartial
      );
      fs.writeFileSync(
        path.join(TEST_PARTIALS_DIR, 'footer.hbs'),
        footerPartial
      );

      const template = `{{>header}}<article>{{{content}}}</article>{{>footer}}`;
      fs.writeFileSync(path.join(TEST_TEMPLATES_DIR, 'page.hbs'), template);

      await build(TEST_CONTENT_DIR, TEST_OUTPUT_DIR, TEST_TEMPLATES_DIR);

      const html = fs.readFileSync(
        path.join(TEST_OUTPUT_DIR, 'partial-test.html'),
        'utf-8'
      );
      expect(html).toContain('<header>My Site</header>');
      expect(html).toContain('<article>');
      expect(html).toContain('<footer>© 2023</footer>');
    });

    it('should handle multiple pages with different templates', async () => {
      const blogPost = `---
title: My Blog Post
template: blog
layout: blog-layout
---
Blog content`;

      const page = `---
title: Regular Page
template: page
layout: default
---
Page content`;

      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'blog.md'), blogPost);
      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page.md'), page);

      const blogTemplate = `<article class="blog">{{{content}}}</article>`;
      const pageTemplate = `<div class="page">{{{content}}}</div>`;
      fs.writeFileSync(path.join(TEST_TEMPLATES_DIR, 'blog.hbs'), blogTemplate);
      fs.writeFileSync(path.join(TEST_TEMPLATES_DIR, 'page.hbs'), pageTemplate);

      const blogLayout = `<div class="blog-wrapper">{{{body}}}</div>`;
      const defaultLayout = `<div class="page-wrapper">{{{body}}}</div>`;
      fs.writeFileSync(
        path.join(TEST_LAYOUTS_DIR, 'blog-layout.hbs'),
        blogLayout
      );
      fs.writeFileSync(
        path.join(TEST_LAYOUTS_DIR, 'default.hbs'),
        defaultLayout
      );

      await build(TEST_CONTENT_DIR, TEST_OUTPUT_DIR, TEST_TEMPLATES_DIR);

      const blogHtml = fs.readFileSync(
        path.join(TEST_OUTPUT_DIR, 'blog.html'),
        'utf-8'
      );
      expect(blogHtml).toContain('class="blog-wrapper"');
      expect(blogHtml).toContain('class="blog"');
      expect(blogHtml).toContain('Blog content');

      const pageHtml = fs.readFileSync(
        path.join(TEST_OUTPUT_DIR, 'page.html'),
        'utf-8'
      );
      expect(pageHtml).toContain('class="page-wrapper"');
      expect(pageHtml).toContain('class="page"');
      expect(pageHtml).toContain('Page content');
    });
  });

  describe('Template not found handling', () => {
    it('should throw error if template is missing', async () => {
      const content = `---
title: Test
template: missing-template
---
Content`;

      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'test.md'), content);
      const pageData = await parseMarkdownFile(
        path.join(TEST_CONTENT_DIR, 'test.md')
      );

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      expect(() => generatePageHtmlWithTemplate(pageData, engine)).toThrow(
        'Template not found'
      );
    });

    it('should handle missing layout gracefully', async () => {
      const content = `---
title: Test
layout: missing-layout
---
Content`;

      fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'test.md'), content);
      const pageData = await parseMarkdownFile(
        path.join(TEST_CONTENT_DIR, 'test.md')
      );

      const template = `<article>{{{content}}}</article>`;
      fs.writeFileSync(path.join(TEST_TEMPLATES_DIR, 'page.hbs'), template);

      const engine = new TemplateEngine({
        templatesDir: TEST_TEMPLATES_DIR,
        layoutsDir: TEST_LAYOUTS_DIR,
        partialsDir: TEST_PARTIALS_DIR,
      });

      const html = generatePageHtmlWithTemplate(pageData, engine);

      expect(html).toContain('<article>');
      expect(html).toContain('Content');
    });
  });
});
