# ssg

A small static site generator for Markdown files.

```sh
npm install
npm run build
npx ssg build
```

By default, Markdown is read recursively from `./content` and HTML is written to `./dist`.

```sh
npx ssg build --content ./posts --output ./public
```

Templates are loaded from `./templates` by default. Use `--templates <dir>` to
choose another directory. Pages use `templates/default.hbs`, or can select a
template and layout in frontmatter:

```markdown
---
title: Hello
template: post
layout: main
---
```

Page templates receive the frontmatter fields plus `title`, `url`, `content`,
`html`, `page`, and `pages`. Markdown HTML should use an unescaped expression,
such as `{{{content}}}`. Layouts live in `templates/layouts` and insert the page
template with `{{{body}}}`. Partials live in `templates/partials` and can be
included with `{{> header}}`; nested partial names use forward slashes.

Pages may start with YAML frontmatter:

```markdown
---
title: Hello
date: 2026-08-16
tags: [news, release]
---

# Welcome
```
