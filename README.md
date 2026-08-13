# Flat-file SSG

A TypeScript CLI that converts Markdown files with optional YAML frontmatter into a static HTML site.

```yaml
---
title: Example post
date: 2024-06-01
tags: [example, news]
---
```

## Usage

```sh
npm install
npm run build
npx ssg build
npx ssg build --content ./articles --output ./public
```

Markdown files are read recursively. Each becomes an HTML file at the matching relative path, and an `index.html` links to every generated page.
