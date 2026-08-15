# Template Engine and Layout Support

This static site generator now supports Handlebars templates with layouts and partials, enabling customizable page rendering while maintaining backward compatibility.

## Directory Structure

The generator looks for templates in the following directory structure:

```
./templates/
├── layouts/           # Layout templates
│   ├── default.hbs    # Default page layout (auto-created)
│   └── index.hbs      # Index/listing layout (auto-created)
├── partials/          # Reusable partial templates
│   └── nav.hbs        # Navigation partial (auto-created)
├── index.hbs          # Index template (auto-created)
└── (other templates)
```

## Default Behavior

If the `./templates` directory exists, the generator automatically:
1. Creates `templates/layouts/default.hbs` - default page layout
2. Creates `templates/layouts/index.hbs` - index page layout
3. Creates `templates/index.hbs` - index page template
4. Creates `templates/partials/nav.hbs` - navigation partial

If the `./templates` directory does **not** exist, the generator falls back to the original inline HTML generation for backward compatibility.

## Using Templates

### 1. Basic Layout Template

A layout template wraps page content with `{{{body}}}` placeholder:

```handlebars
<!DOCTYPE html>
<html>
<head>
  <title>{{title}}</title>
</head>
<body>
  {{>nav}}
  <article>
    <h1>{{title}}</h1>
    {{{body}}}
  </article>
</body>
</html>
```

### 2. Specifying Layout in Frontmatter

Pages can specify a custom layout in frontmatter:

```markdown
---
title: My Page
layout: custom.hbs
---

# Page Content

This uses the custom layout.
```

### 3. Available Variables in Templates

Templates have access to page metadata:

```markdown
---
title: Post Title
date: 2024-01-15
tags: typescript, testing
author: John Doe
---
```

In templates, access these via Handlebars:
- `{{title}}` - page title
- `{{date}}` - publication date
- `{{tags}}` - array of tags (iterate with `{{#each tags}}`)
- `{{author}}` - custom metadata fields
- `{{{body}}}` - rendered page content (unescaped)
- `{{slug}}` - page slug/filename

### 4. Conditional Rendering

Use Handlebars conditionals in templates:

```handlebars
{{#if date}}
  <p class="date">Published: {{date}}</p>
{{/if}}

{{#if tags}}
  <div class="tags">
    {{#each tags}}
      <span class="tag">{{this}}</span>
    {{/each}}
  </div>
{{/if}}
```

### 5. Partials/Includes

Partials are reusable template fragments. Include them with `{{>partialName}}`:

**templates/partials/nav.hbs:**
```handlebars
<nav>
  <a href="index.html">← Home</a>
</nav>
```

**templates/layouts/default.hbs:**
```handlebars
<html>
  <body>
    {{>nav}}
    {{{body}}}
  </body>
</html>
```

All `.hbs` files in `templates/partials/` are automatically registered.

## Handlebars Features

The template engine supports full Handlebars syntax:

```handlebars
{{! Comments }}
{{#if condition}}...{{/if}}
{{#each array}}...{{/each}}
{{#with object}}...{{/with}}
{{variable}}
{{{unescaped_variable}}}
{{>partial}}
```

## Example Project Structure

```
project/
├── content/
│   ├── about.md
│   ├── blog-post.md
│   └── home.md
├── templates/
│   ├── layouts/
│   │   ├── default.hbs      # Regular page layout
│   │   ├── blog.hbs         # Blog post layout with date/tags
│   │   └── index.hbs        # Index listing layout
│   ├── partials/
│   │   ├── nav.hbs
│   │   ├── header.hbs
│   │   └── footer.hbs
│   └── index.hbs            # Index template
├── dist/                    # Generated output
└── package.json
```

## Default Templates

### Default Layout (templates/layouts/default.hbs)

Includes:
- Page title in `<title>` and `<h1>`
- Navigation partial
- Conditional date display
- Conditional tags display
- Basic CSS styling
- Page content via `{{{body}}}`

### Index Layout (templates/layouts/index.hbs)

Includes:
- List of all pages with links
- Conditional date display per page
- Basic CSS styling

## CLI Usage

Templates are automatically detected. If a `./templates` directory exists, it will be used:

```bash
ssg build --content ./content --output ./dist
```

The generator looks for templates in these default locations:
- `--templates` (optional, default: `./templates`)
- `--layouts-dir` (optional, default: `./templates/layouts`)
- `--partials-dir` (optional, default: `./templates/partials`)

## Migration from Inline HTML

To migrate existing sites to use templates:

1. Create `templates/layouts/default.hbs` with your desired layout
2. Move any common header/footer to `templates/partials/`
3. Customize styling and structure
4. Generator will automatically use templates if the directory exists

No changes needed to markdown files - they work as-is.

## Template Caching

Templates are compiled and cached in memory for performance. Changes to template files require restarting the build process.

## Error Handling

- If a specified layout doesn't exist, an error is thrown
- If templates directory doesn't exist, falls back to inline HTML generation
- Template syntax errors are reported during generation
