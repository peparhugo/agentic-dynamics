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

Pages may start with YAML frontmatter:

```markdown
---
title: Hello
date: 2026-08-16
tags: [news, release]
---

# Welcome
```
