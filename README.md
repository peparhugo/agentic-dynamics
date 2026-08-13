# ssg

A small TypeScript static site generator backed entirely by Markdown files.

## Usage

```sh
npm install
npm run build
npx ssg build
npx ssg build --content ./posts --output ./public
npx ssg build --templates ./templates
```

Markdown files may include `title`, `date`, and `tags` frontmatter:

```markdown
---
title: Example page
date: 2024-05-01
tags: [example, news]
---

# Page content
```

## Templates

Handlebars templates live in `templates/`. A page may select one with `template`
frontmatter; otherwise `templates/default.hbs` is used when present. Templates
receive all frontmatter fields and the rendered Markdown as both `content` and
`body`.

```markdown
---
title: About
template: page
layout: default
---
```

Layouts live in `templates/layouts/` and must use `{{{body}}}` for rendered page
content. `templates/layouts/default.hbs` is applied by default when present.
Reusable partials live in `templates/partials/` and can be included by filename,
for example `{{> header}}`. Set `template: false` or `layout: false` to skip a
default template or layout for a page. Without template files, the original
built-in page output remains unchanged.
