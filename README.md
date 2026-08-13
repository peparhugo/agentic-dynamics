# ssg

A small static site generator that turns Markdown files into HTML.

## Usage

```sh
npm install
npm run build
npx ssg build
```

By default, Markdown is read from `./content` and HTML is written to `./dist`.
Use `--content` and `--output` to select different directories:

```sh
npx ssg build --content posts --output public
```

Markdown files can include YAML frontmatter:

```markdown
---
title: Hello
date: 2026-08-13
tags: [news, example]
---

# Hello
```
