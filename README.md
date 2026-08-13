# ssg

A TypeScript CLI that turns Markdown files with optional frontmatter into a static HTML site.

```yaml
---
title: My post
date: 2024-01-15
tags: [news, updates]
---

# Hello
```

## Usage

Install dependencies and compile the CLI (package code is written to `./lib`):

```sh
npm install
npm run build
npx ssg build
```

Content is read recursively from `./content` and HTML is written to `./dist`. Override either location with:

```sh
npx ssg build --content ./articles --output ./public
```

Run tests with `npm test`.
