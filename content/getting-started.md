---
title: Getting Started
date: 2024-08-14
tags: [guide, setup]
---

# Getting Started with the Static Site Generator

## Installation

Install dependencies:

```bash
npm install
```

## Building Your Site

Run the build command:

```bash
npm run build
npx ssg build --content ./content --output ./dist
```

## Creating Content

Add `.md` files to your content directory with frontmatter:

```markdown
---
title: Your Page Title
date: 2024-08-15
tags: [tag1, tag2]
---

# Your Content Here

Write your markdown content below the frontmatter.
```

## Directory Structure

```
.
├── content/          # Your markdown files
├── dist/             # Generated HTML files
├── src/              # TypeScript source code
└── package.json
```

That's it! Your static site is ready to deploy.
