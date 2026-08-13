# ssg

A small TypeScript static site generator for Markdown files with YAML frontmatter.

```sh
npm install
npm run build
npx ssg build
```

The command reads `./content` and writes the generated site to `./dist`. Use custom paths with:

```sh
npx ssg build --content posts --output public
```

Frontmatter can define `title`, `date`, and `tags`:

```md
---
title: First post
date: 2026-08-13
tags: [news, example]
---

# Hello
```
