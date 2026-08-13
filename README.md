# ssg

A small TypeScript static site generator backed entirely by Markdown files.

## Usage

```sh
npm install
npm run build
npx ssg build
npx ssg build --content ./posts --output ./public
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
