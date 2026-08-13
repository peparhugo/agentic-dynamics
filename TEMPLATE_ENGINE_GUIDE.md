# Template Engine and Layout Support Guide

## Overview

The static site generator now supports Handlebars templates with layouts and partials, enabling flexible and reusable page designs.

## Directory Structure

```
project/
├── templates/              # Template files
│   ├── post.hbs           # Template for blog posts
│   ├── page.hbs           # Template for pages
│   ├── layouts/           # Layout templates
│   │   ├── default.hbs    # Default page layout
│   │   └── blog.hbs       # Blog post layout
│   └── partials/          # Reusable components
│       ├── header.hbs     # Site header
│       ├── footer.hbs     # Site footer
│       └── nav.hbs        # Navigation
├── content/               # Markdown content files
│   └── posts/
│       ├── first-post.md
│       └── second-post.md
└── dist/                  # Generated HTML output
```

## Usage

### Basic Command with Templates

```bash
# Build with default templates directory
npm run build
npx ssg build --templates ./templates

# With custom directories
npx ssg build --content ./posts --output ./website --templates ./templates
```

### Markdown Frontmatter

Specify template and layout for each page:

```markdown
---
title: My Blog Post
date: "2024-01-15"
tags:
  - typescript
  - web
template: post
layout: blog
---

# Content

Your markdown content here...
```

## Template Syntax

Templates use Handlebars syntax with the following available variables:

### Basic Variables

- `{{title}}` - Page title
- `{{date}}` - Publication date
- `{{slug}}` - Page slug
- `{{author}}` - Author (if provided)
- Any custom frontmatter property (e.g., `{{category}}`, `{{tags}}`)

### Arrays and Loops

```handlebars
{{#each tags}}
  <span class="tag">{{this}}</span>
{{/each}}
```

### Conditionals

```handlebars
{{#if date}}
  <p>Published: {{date}}</p>
{{/if}}

{{#if tags}}
  <div class="tags">
    {{#each tags}}
      <span>{{this}}</span>
    {{/each}}
  </div>
{{/if}}
```

### Raw HTML

Use triple braces `{{{body}}}` to render HTML without escaping:

```handlebars
<article>
  {{{body}}}
</article>
```

Escaped HTML with double braces `{{variable}}` prevents XSS:

```handlebars
<h1>{{title}}</h1>
```

## Template Files

### Page Template Example

File: `templates/post.hbs`

```handlebars
<article class="post">
  <h1>{{title}}</h1>
  {{#if date}}
    <div class="date">{{date}}</div>
  {{/if}}
  {{#if tags}}
    <div class="tags">
      {{#each tags}}
        <span class="tag">{{this}}</span>
      {{/each}}
    </div>
  {{/if}}
  <div class="content">
    {{{body}}}
  </div>
</article>
```

### Layout Files

Layouts wrap template output with site-wide structure.

File: `templates/layouts/blog.hbs`

```handlebars
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{title}}</title>
</head>
<body>
  {{> header}}
  <main>
    {{{body}}}
  </main>
  {{> footer}}
</body>
</html>
```

### Partial Files

Reusable components included in templates and layouts.

File: `templates/partials/header.hbs`

```handlebars
<header>
  <nav>
    <a href="/">Home</a>
    <a href="/about">About</a>
    <a href="/blog">Blog</a>
  </nav>
</header>
```

File: `templates/partials/footer.hbs`

```handlebars
<footer>
  <p>&copy; 2024 My Site</p>
</footer>
```

## Processing Order

1. **Content Parsing**: Markdown file → HTML + frontmatter
2. **Template Application** (if specified): HTML wrapped in template
3. **Layout Application** (if specified): Templated HTML wrapped in layout
4. **Default Fallback**: If no template/layout, use raw HTML content

## API

### TemplateEngine Class

```typescript
import { TemplateEngine } from './template-engine';

const engine = new TemplateEngine({
  templateDir: './templates'
});

// Render with all options
const html = engine.renderPage(page, 'post', 'blog');

// Render with template only
const html = engine.renderPage(page, 'post');

// Render with layout only
const html = engine.renderPage(page, undefined, 'blog');

// Check if template/layout exists
const hasTemplate = engine.hasTemplate('post');
const hasLayout = engine.hasLayout('blog');
```

### Generator Function

```typescript
import { generatePageHTML } from './generator';
import { TemplateEngine } from './template-engine';

const engine = new TemplateEngine({ templateDir: './templates' });

// With template engine (new feature)
const html = generatePageHTML(page, engine);

// Without template engine (default behavior - backward compatible)
const html = generatePageHTML(page);
```

## Backward Compatibility

- ✅ Existing code continues to work without changes
- ✅ generatePageHTML works with or without templateEngine parameter
- ✅ Pages can omit template/layout for default behavior
- ✅ All existing tests pass unchanged

## Features

✅ **Handlebars Templates**
- Full Handlebars syntax support
- Conditionals, loops, helpers

✅ **Layouts**
- Wrap template output with site structure
- {{{body}}} placeholder for content

✅ **Partials**
- Reusable components
- Automatic loading from templates/partials/
- Include with {{> partialName}}

✅ **Template Caching**
- Compiled templates cached for performance
- Reusable across page renders

✅ **Error Handling**
- Clear error messages for missing templates
- Graceful fallback to default if templates unavailable

✅ **Security**
- HTML escaping with double braces {{}}
- Raw HTML with triple braces {{{}}} only when needed

## Example: Complete Blog Setup

### Templates Structure

```
templates/
├── blog.hbs          # Blog post template
├── page.hbs          # Regular page template
├── layouts/
│   ├── blog.hbs      # Blog layout with sidebar
│   └── default.hbs   # Default layout
└── partials/
    ├── header.hbs
    ├── footer.hbs
    ├── nav.hbs
    └── sidebar.hbs
```

### Content

```markdown
---
title: Getting Started with TypeScript
date: "2024-01-15"
tags:
  - typescript
  - tutorial
template: blog
layout: blog
category: tutorials
---

# Getting Started

Your content here...
```

### Output

When built, this generates an HTML file with:
- Custom template styling and structure
- Layout wrapping with header, nav, sidebar, footer
- All partial components included
- All metadata accessible in templates

## Troubleshooting

**Template not found error**
- Check that .hbs file exists in correct directory
- Ensure filename matches template name (without .hbs extension)

**Partial not rendering**
- Verify partial file is in templates/partials/
- Use {{> partialName}} syntax (no .hbs extension)
- Check for typos in partial name

**Body not appearing in layout**
- Ensure layout uses {{{body}}} (triple braces for raw HTML)
- Double braces {{body}} would escape the HTML

**Custom variables not available**
- Add them to frontmatter in markdown file
- Access in templates with {{variableName}}
