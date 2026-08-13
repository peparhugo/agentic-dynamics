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
```

Markdown files are discovered recursively. Their relative paths are preserved with an `.html` extension, and an `index.html` containing links to every page is generated in the output directory.
