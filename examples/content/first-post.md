---
title: Getting Started with Templates
template: post
layout: blog
author: Jane Doe
date: 2024-01-15
tags: tutorial, templates, handlebars
---

# Getting Started with Templates

This blog post demonstrates how to use the template and layout system in our static site generator.

## What Are Templates?

Templates are Handlebars (.hbs) files that define how your content is rendered. They can include:

- **Variables**: `{{title}}`, `{{content}}`, `{{date}}`
- **Conditionals**: `{{#if condition}}...{{/if}}`
- **Loops**: `{{#each items}}...{{/each}}`
- **Partials**: `{{>header}}`, `{{>footer}}`

## Directory Structure

Place templates in these directories:

```
./templates/
  page.hbs           # Content templates
  post.hbs
  layouts/
    default.hbs      # Layout wrappers
    blog.hbs
  partials/
    header.hbs       # Reusable components
    footer.hbs
```

## Using Frontmatter

Specify which template and layout to use in your markdown frontmatter:

```yaml
---
title: Post Title
template: post        # Which template file to use
layout: blog          # Which layout to wrap with
author: Your Name
date: 2024-01-15
tags: tag1, tag2
---
```

## Key Features

- **Backward Compatible**: Pages without template/layout specs use default HTML
- **Fallback Support**: Missing templates fall back to built-in HTML generation
- **Custom Fields**: Any frontmatter field is passed to templates
- **Partials Support**: Create reusable header, footer, nav components

Happy building! 🎉
