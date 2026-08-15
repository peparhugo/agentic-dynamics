# Template System Examples

This directory contains example templates, layouts, and content to demonstrate the template engine and layout support.

## Directory Structure

```
examples/
├── content/              # Markdown files with template configuration
│   ├── about.md         # Page using 'page' template
│   ├── first-post.md    # Blog post using 'post' template
│   └── handlebars-tips.md
├── templates/
│   ├── page.hbs         # Content template for pages
│   ├── post.hbs         # Content template for blog posts
│   ├── layouts/
│   │   ├── default.hbs  # Default page layout
│   │   └── blog.hbs     # Blog post layout
│   └── partials/
│       ├── header.hbs   # Reusable header component
│       └── footer.hbs   # Reusable footer component
└── README.md
```

## Using This Example

To build the example site:

```bash
# From the project root
node dist/index.js build --content examples/content --output examples/dist
```

## Template Features Demonstrated

### 1. **Templates** (templates/*.hbs)
Define how content is rendered with access to frontmatter variables.

**page.hbs**: Simple page template showing title, date, tags, and content.

**post.hbs**: Blog post template with author, date, and tag display.

### 2. **Layouts** (templates/layouts/*.hbs)
Wrap templates with consistent HTML structure.

**default.hbs**: Clean layout for general pages with navigation.

**blog.hbs**: Styled layout specifically for blog posts.

### 3. **Partials** (templates/partials/*.hbs)
Reusable components included in layouts.

**header.hbs**: Site header with navigation.

**footer.hbs**: Site footer with copyright and social links.

## Frontmatter Configuration

Each markdown file can specify which template and layout to use:

```yaml
---
title: Page Title
template: page        # Which template file to use (without .hbs)
layout: default       # Which layout to wrap with (without .hbs)
date: 2024-01-15
tags: tag1, tag2
author: Author Name
---
```

### Available Templates
- `page` - For regular pages
- `post` - For blog posts

### Available Layouts
- `default` - General purpose layout
- `blog` - Specialized blog post layout

## Frontmatter Variables

All frontmatter fields are available in templates:

- `title` - Page title (required)
- `date` - Publication date
- `tags` - Comma-separated tags
- `author` - Content author (for posts)
- `template` - Template file to use
- `layout` - Layout file to wrap with
- Any custom fields you define

These appear as `{{variableName}}` in your templates.

## Handlebars Features Used

### Variables
```handlebars
{{title}}
{{date}}
{{author}}
{{{content}}}  <!-- Use triple braces for HTML -->
```

### Conditionals
```handlebars
{{#if date}}
  <time>{{date}}</time>
{{/if}}
```

### Loops
```handlebars
{{#each tags}}
  <span>{{this}}</span>
{{/each}}
```

### Partials
```handlebars
{{>header}}
<main>{{{body}}}</main>
{{>footer}}
```

## Building Your Own Templates

1. Create `.hbs` files in `templates/` directory
2. Create layout files in `templates/layouts/`
3. Create reusable partials in `templates/partials/`
4. Reference them in markdown frontmatter with `template:` and `layout:` fields

## Backward Compatibility

If you don't specify `template` or `layout`, the generator falls back to the built-in HTML generation, maintaining 100% backward compatibility with existing markdown files that don't use the template system.

## Tips

- Use `{{{body}}}` (triple braces) in layouts to render page HTML without escaping
- Use `{{variable}}` (double braces) for text to auto-escape HTML entities
- Partials are automatically loaded from `templates/partials/`
- Templates are cached for performance
- Custom frontmatter fields can be passed to templates and used with conditionals
