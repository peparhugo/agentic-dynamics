# Static Site Generator (SSG) CLI

A TypeScript-based static site generator with frontmatter support, Handlebars templates, layouts, and automatic index generation.

## Features

- Read Markdown files from a content directory
- Parse Markdown to HTML with frontmatter support (title, date, tags)
- **NEW:** Handlebars template engine with layouts and partials
- **NEW:** Specify templates and layouts per-page via frontmatter
- Generate an `index.html` listing all pages (sorted by date)
- Create individual HTML files for each page
- TypeScript with strict mode
- Comprehensive test suite with Jest

## Installation

```bash
npm install
```

## Building

```bash
npm run build
```

## Usage

```bash
# Using default directories (./content → ./dist)
npx ssg build

# Using custom directories
npx ssg build --content ./my-content --output ./my-output

# With templates support
npx ssg build --templates ./templates

# All options combined
npx ssg build --content ./posts --output ./website --templates ./templates
```

## Project Structure

```
src/
├── cli.ts                    # Main CLI entry point
├── parser.ts                 # Markdown parser with frontmatter
├── generator.ts              # HTML generator functions
├── template-engine.ts        # Handlebars template engine
└── __tests__/
    ├── parser.test.ts        # Parser unit tests
    ├── generator.test.ts      # Generator unit tests
    ├── cli.test.ts           # Integration tests
    └── template-engine.test.ts # Template engine tests

templates/
├── layouts/                  # Page layout templates
│   ├── default.hbs
│   └── blog.hbs
├── partials/                 # Reusable components
│   ├── header.hbs
│   ├── footer.hbs
│   └── nav.hbs
└── post.hbs                  # Page templates
```

## Content Format

Create Markdown files in your content directory with YAML frontmatter:

```markdown
---
title: My Post Title
date: 2024-01-15
tags:
  - typescript
  - testing
template: post
layout: blog
---

# Content

Your markdown content here...
```

### Frontmatter Options

- `title` (required) - Page title
- `date` (optional) - Publication date
- `tags` (optional) - Array of tags
- `template` (optional) - Handlebars template file name (without .hbs)
- `layout` (optional) - Layout template file name (without .hbs)
- Custom properties - Any other YAML properties are available in templates

## Templates

Use Handlebars templates to customize page rendering. See [TEMPLATE_ENGINE_GUIDE.md](TEMPLATE_ENGINE_GUIDE.md) for detailed documentation.

### Template Example

File: `templates/post.hbs`

```handlebars
<article>
  <h1>{{title}}</h1>
  {{#if date}}<p>Published: {{date}}</p>{{/if}}
  {{#if tags}}
    <div class="tags">
      {{#each tags}}<span>{{this}}</span>{{/each}}
    </div>
  {{/if}}
  <div class="content">
    {{{body}}}
  </div>
</article>
```

### Layout Example

File: `templates/layouts/blog.hbs`

```handlebars
<!DOCTYPE html>
<html>
  <head><title>{{title}}</title></head>
  <body>
    {{> header}}
    <main>{{{body}}}</main>
    {{> footer}}
  </body>
</html>
```

### Partial Example

File: `templates/partials/header.hbs`

```handlebars
<header>
  <h1>My Blog</h1>
  <nav><a href="/">Home</a></nav>
</header>
```

## Output

The generator creates:
- Individual HTML files for each post (e.g., `my-post.html`)
- `index.html` with links to all pages, sorted by date (newest first)

## Testing

```bash
npm test
```

Comprehensive test suite with coverage for:
- **Parser Tests** (6 tests) - Markdown parsing and frontmatter extraction
- **Generator Tests** (10 tests) - HTML generation with proper escaping and sorting
- **CLI Integration Tests** (4 tests) - CLI functionality and directory handling
- **Template Engine Tests** (19 tests) - Handlebars templates, layouts, partials, caching
  - Template rendering and fallback behavior
  - Layout wrapping and partial includes
  - Conditional and loop expressions
  - HTML escaping and security

Total: 39 tests
