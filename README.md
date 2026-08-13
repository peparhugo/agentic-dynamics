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

Frontmatter supports `title`, `date`, and either array or comma-separated `tags`:

```md
---
title: Hello
date: 2026-08-13
tags: [news, updates]
---

# Welcome
```
