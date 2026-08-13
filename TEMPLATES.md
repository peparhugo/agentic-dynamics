# Template Engine Documentation

This static site generator now supports Handlebars templates for flexible page rendering with layouts and partials.

## Directory Structure

```
templates/
├── page.hbs              # Default page template
├── blog.hbs             # Example blog template
├── layouts/
│   ├── default.hbs      # Default layout wrapper
│   └── blog-layout.hbs  # Example blog layout
└── partials/
    ├── header.hbs       # Header partial
    └── footer.hbs       # Footer partial
```

## Features

### 1. Templates
Templates are Handlebars files that render individual page content.

**Default Template**: `page.hbs`

Example template (`templates/page.hbs`):
```handlebars
<article class="page">
  <h1>{{title}}</h1>
  {{#if date}}<p class="date">{{date}}</p>{{/if}}
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

### 2. Layouts
Layouts wrap rendered template output to provide page structure.

**Default Layout**: `default.hbs`

The layout receives a `body` variable with the rendered template output:

Example layout (`templates/layouts/default.hbs`):
```handlebars
<!DOCTYPE html>
<html>
<head>
  <title>{{title}}</title>
</head>
<body>
  {{>header}}
  <main>{{{body}}}</main>
  {{>footer}}
</body>
</html>
```

### 3. Partials
Partials are reusable template fragments included in templates and layouts.

Located in `templates/partials/`:
- `header.hbs` - Navigation and header
- `footer.hbs` - Footer content
- `nav.hbs` - Navigation menu
- etc.

Include partials with the `{{>partial-name}}` syntax.

## Frontmatter Options

Pages can specify which template and layout to use via frontmatter:

```markdown
---
title: My Page
date: 2024-01-15
tags: [javascript, templates]
template: blog          # Use templates/blog.hbs
layout: blog-layout     # Use templates/layouts/blog-layout.hbs
---

# Page Content

Your markdown content here...
```

### Default Values
- If `template` is not specified: uses `page` (from `templates/page.hbs`)
- If `layout` is not specified: uses `default` (from `templates/layouts/default.hbs`)

## Template Context Variables

All frontmatter fields are available in templates:

| Variable | Description |
|----------|-------------|
| `title` | Page title from frontmatter |
| `date` | Publication date |
| `tags` | Array of tags |
| `slug` | Page slug (filename without .md) |
| `filename` | Original markdown filename |
| `content` | Rendered HTML content |
| `...` | Any custom frontmatter fields |

## Handlebars Syntax

### Variables
```handlebars
{{title}}              # Outputs the title
{{{content}}}          # Outputs HTML without escaping
{{slug}}               # Outputs the slug
```

### Conditionals
```handlebars
{{#if date}}
  <p>Published: {{date}}</p>
{{/if}}

{{#if published}}
  Published
{{else}}
  Draft
{{/if}}
```

### Loops
```handlebars
{{#each tags}}
  <span class="tag">{{this}}</span>
{{/each}}

{{#each pages}}
  <a href="{{slug}}.html">{{title}}</a>
{{/each}}
```

### Partials
```handlebars
{{>header}}
{{>footer}}
{{>navigation}}
```

## Usage with CLI

Build with default templates:
```bash
npm run build
# Uses ./templates directory
```

Build with custom templates directory:
```bash
npm run build
ssg build --templates ./my-templates
```

Build without templates (uses fallback HTML generation):
```bash
ssg build --content ./content --output ./dist --templates ./nonexistent
```

## Example Workflow

1. Create a content markdown file:
```markdown
---
title: My First Blog Post
date: 2024-01-15
tags: [nodejs, templates]
template: blog
layout: blog-layout
---

# Introduction

This is my first blog post using templates!
```

2. Create `templates/blog.hbs`:
```handlebars
<article class="blog-post">
  <h1>{{title}}</h1>
  <p class="meta">{{date}} • {{tags.length}} tags</p>
  <div class="content">
    {{{content}}}
  </div>
</article>
```

3. Create `templates/layouts/blog-layout.hbs`:
```handlebars
<!DOCTYPE html>
<html>
<head>
  <title>{{title}} - Blog</title>
</head>
<body>
  {{>header}}
  <main>{{{body}}}</main>
  {{>footer}}
</body>
</html>
```

4. Build the site:
```bash
npm run build
```

The output will be a fully rendered HTML file with proper structure, styling, and all partials included.

## Backwards Compatibility

Pages without templates still work! If no templates directory exists, the generator falls back to the original HTML generation. Existing content without frontmatter template specifications continues to work as before.

## Custom Helpers

The template engine can be extended with custom Handlebars helpers:

```typescript
import { createTemplateEngine } from './templates';

const engine = createTemplateEngine();
engine.registerHelper('uppercase', (str) => String(str).toUpperCase());
```

Then in templates:
```handlebars
{{uppercase title}}
```
