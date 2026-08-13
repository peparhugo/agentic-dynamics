# ssg

A small TypeScript CLI that turns Markdown files with optional YAML frontmatter into a static HTML site.

```yaml
---
title: Example post
date: 2025-02-03
tags: [news, typescript]
---

# Hello
```

## Usage

```sh
npm install
npm run build
npx ssg build
npx ssg build --content ./posts --output ./public
npx ssg build --templates ./templates
```

Markdown files are discovered recursively. Their relative paths are preserved with an `.html` extension, and an `index.html` containing links to every page is generated in the output directory.

## Templates

Handlebars templates use this structure:

```text
templates/
  default.hbs
  post.hbs
  layouts/
    base.hbs
  partials/
    header.hbs
```

`default.hbs` is used when a page does not select a template. Select templates and layouts in frontmatter:

```yaml
---
title: Example
template: post
layout: base
---
```

Templates receive frontmatter plus `title`, `date`, `tags`, `url`, and the rendered Markdown as `{{{content}}}`. Layouts receive the rendered page as `{{{body}}}`. Files under `partials/` are available by relative name, such as `{{> header}}`.
