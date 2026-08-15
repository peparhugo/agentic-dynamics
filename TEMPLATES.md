# Template Engine & Layout System

## Overview

The static site generator now includes a powerful Handlebars-based template engine that allows you to define custom page templates and layouts for your site. This feature is completely optional and backward compatible - existing sites without templates continue to work exactly as before.

## Features

- **Handlebars Templates** - Use the familiar Handlebars syntax for templates
- **Layout System** - Wrap page content with consistent HTML structure
- **Partial Includes** - Reusable components for headers, footers, navigation
- **Frontmatter Configuration** - Specify template and layout per page in YAML
- **Template Caching** - Compiled templates are cached for performance
- **Fallback Support** - Missing templates gracefully fall back to built-in HTML
- **Custom Fields** - Any frontmatter field can be used in templates

## Quick Start

### 1. Create Template Directory Structure

```bash
templates/
├── layouts/
│   ├── default.hbs
│   └── blog.hbs
├── partials/
│   ├── header.hbs
│   └── footer.hbs
├── page.hbs
└── post.hbs
```

### 2. Create a Layout Template

**templates/layouts/default.hbs**:
```handlebars
<!DOCTYPE html>
<html>
<head>
  <title>{{title}} - My Site</title>
</head>
<body>
  <header>
    <h1>My Site</h1>
  </header>
  <main>
    {{{body}}}
  </main>
  <footer>
    <p>&copy; 2024</p>
  </footer>
</body>
</html>
```

### 3. Create a Content Template

**templates/page.hbs**:
```handlebars
<article>
  <h1>{{title}}</h1>
  {{#if date}}<p>Published: {{date}}</p>{{/if}}
  <div class="content">
    {{{content}}}
  </div>
</article>
```

### 4. Create Markdown Content

**content/about.md**:
```markdown
---
title: About Me
template: page
layout: default
---

# About

This is my about page.
```

### 5. Build Your Site

```bash
node dist/index.js build --content content --output dist
```

## Directory Structure

The template engine looks for templates in this structure:

```
templates/
├── *.hbs              # Content templates (page.hbs, post.hbs, etc.)
├── layouts/
│   └── *.hbs          # Layout templates (default.hbs, blog.hbs, etc.)
└── partials/
    └── *.hbs          # Partial includes (header.hbs, footer.hbs, etc.)
```

### Custom Template Directory

By default, templates are looked for in `./templates/`. You can specify a custom directory:

```bash
node dist/index.js build --content content --output dist --templatesDir custom/templates
```

## Template Configuration

### Frontmatter Fields

Each markdown file can specify which template and layout to use:

```yaml
---
title: Page Title
template: page          # Template file to use (without .hbs)
layout: default         # Layout file to wrap with (without .hbs)
date: 2024-01-15
tags: tag1, tag2
author: Author Name
customField: value
---
```

### Available Variables in Templates

All frontmatter fields are available:
- `{{title}}` - Page title
- `{{date}}` - Publication date
- `{{tags}}` - Array of tags
- `{{author}}` - Author name
- `{{content}}` - The rendered markdown HTML
- `{{customField}}` - Any custom field from frontmatter
- `{{body}}` - Available only in layouts (the rendered template)

## Handlebars Syntax

### Variables

```handlebars
<!-- Double braces escape HTML -->
<h1>{{title}}</h1>

<!-- Triple braces render raw HTML (use in layouts for body) -->
<main>{{{body}}}</main>
```

### Conditionals

```handlebars
{{#if condition}}
  <p>This shows if condition is true</p>
{{else}}
  <p>This shows otherwise</p>
{{/if}}
```

### Loops

```handlebars
{{#each items}}
  <li>{{this}}</li>
{{/each}}
```

### Partials

```handlebars
<!-- Include templates/partials/header.hbs -->
{{>header}}

<!-- Include templates/partials/footer.hbs -->
{{>footer}}
```

## Real-World Examples

### Blog Post Template

**templates/post.hbs**:
```handlebars
<article class="blog-post">
  <header>
    <h1>{{title}}</h1>
    {{#if author}}<p class="author">By {{author}}</p>{{/if}}
    {{#if date}}<time>{{date}}</time>{{/if}}
  </header>
  {{#if tags}}
  <div class="tags">
    {{#each tags}}<span class="tag">{{this}}</span>{{/each}}
  </div>
  {{/if}}
  <div class="content">
    {{{content}}}
  </div>
</article>
```

### Blog Layout

**templates/layouts/blog.hbs**:
```handlebars
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>{{title}} - My Blog</title>
  <style>
    body { font-family: Georgia, serif; line-height: 1.8; }
    article { max-width: 800px; margin: 0 auto; }
  </style>
</head>
<body>
  {{>blog-header}}
  <main>{{{body}}}</main>
  {{>blog-footer}}
</body>
</html>
```

### Header Partial

**templates/partials/blog-header.hbs**:
```handlebars
<header class="site-header">
  <h1>My Blog</h1>
  <nav>
    <a href="index.html">Home</a>
    <a href="posts.html">All Posts</a>
  </nav>
</header>
```

## Important Notes

### HTML Escaping

In Handlebars:
- `{{variable}}` - Escapes HTML entities (safe for text)
- `{{{variable}}}` - Renders raw HTML (use for content and body)

In layout templates, always use triple braces for body:
```handlebars
<!-- Correct -->
<main>{{{body}}}</main>

<!-- Wrong - will escape HTML -->
<main>{{body}}</main>
```

### Template Not Found

If a template file doesn't exist:
1. The generator looks for the default page template (`templates/page.hbs`)
2. If no layout is found, it skips layout wrapping
3. If no template system is available, it falls back to built-in HTML generation

This ensures backward compatibility and graceful degradation.

### Partial Registration

Partials are automatically registered when the TemplateEngine is created:
- Files in `templates/partials/` are registered by their filename (without .hbs)
- Use `{{>header}}` to include `templates/partials/header.hbs`
- Partials inherit template data

## API Reference

### Building with Custom Options

```typescript
import { SiteGenerator } from './src/generator.js';

const generator = new SiteGenerator({
  contentDir: './content',
  outputDir: './dist',
  templatesDir: './templates'  // Optional, defaults to './templates'
});

await generator.build();
```

### TemplateEngine Class

```typescript
import { TemplateEngine } from './src/template-engine.js';

const engine = new TemplateEngine('./templates');

// Render a template
const html = engine.renderTemplate(
  './templates/page.hbs',
  { title: 'Page', content: '<p>Hello</p>' }
);

// Render with layout
const page = engine.renderPageTemplate(
  'page',
  { title: 'Page', content: '<p>Hello</p>' },
  'default'  // layout name
);

// Check if layout exists
if (engine.hasLayout('blog')) { }

// List available templates
const templates = engine.getAvailableTemplates();

// List available layouts
const layouts = engine.getAvailableLayouts();
```

## Migration from Static HTML

If you're currently using the generator's built-in HTML and want to switch to custom templates:

1. Create the `templates/` directory structure
2. Create your layout and partial templates
3. Add `template: page` and `layout: default` to frontmatter
4. Build and test - existing pages without template config still work
5. Gradually migrate pages to new templates

No existing functionality is broken - this is a purely additive feature.

## Performance

- Templates are compiled once and cached in memory
- Partials are registered at engine initialization
- No file I/O during template rendering
- Efficient for large sites with many pages

## Troubleshooting

### Templates not rendering
- Ensure template directory exists: `./templates/`
- Check template filenames use `.hbs` extension
- Verify frontmatter specifies correct `template` and `layout` names

### HTML being escaped
- Use `{{{body}}}` in layouts, not `{{body}}`
- Use `{{{content}}}` in templates, not `{{content}}`

### Partial not found
- Ensure partial files are in `templates/partials/`
- Use partial name without `.hbs`: `{{>header}}` not `{{>header.hbs}}`

### Fallback to default HTML
- Check console for template errors
- Verify template file syntax (Handlebars syntax error)
- Ensure layout file exists if specified
