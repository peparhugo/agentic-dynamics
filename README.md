# ssg

A small static site generator that turns Markdown files into HTML pages.

```sh
npm install
npm run build
npx ssg build
```

Markdown is read from `./content` and HTML is written to `./dist`. Override those directories when needed:

```sh
npx ssg build --content posts --output public
```

Templates are read from `./templates` (or set with `--templates`). A page can select a
Handlebars template and layout in its frontmatter:

```md
---
title: Hello
template: post
layout: site
---
```

`templates/default.hbs` is used when `template` is omitted. Layouts belong in
`templates/layouts` and insert rendered page content with `{{{body}}}`. Reusable
partials belong in `templates/partials` and can be included with `{{> header}}`.
Templates support escaped `{{value}}`, raw `{{{value}}}`, `{{#if value}}`, and
`{{#each values}}` expressions.

Frontmatter supports `title`, `date`, and either array or comma-separated `tags`:

```md
---
title: Hello
date: 2026-08-13
tags: [news, updates]
---

# Welcome
```
