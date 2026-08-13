# Static Site Generator (SSG) CLI

A TypeScript-based static site generator with frontmatter support and automatic index generation.

## Features

- Read Markdown files from a content directory
- Parse Markdown to HTML with frontmatter support (title, date, tags)
- Generate an `index.html` listing all pages (sorted by date)
- Create individual HTML files for each page
- TypeScript with strict mode
- Comprehensive test suite with Jest

## Installation

```bash
npm install
```

## Building

```bash
npm run build
```

## Usage

```bash
# Using default directories (./content → ./dist)
npx ssg build

# Using custom directories
npx ssg build --content ./my-content --output ./my-output
```

## Project Structure

```
src/
├── cli.ts              # Main CLI entry point
├── parser.ts           # Markdown parser with frontmatter
├── generator.ts        # HTML generator functions
└── __tests__/
    ├── parser.test.ts   # Parser unit tests
    ├── generator.test.ts # Generator unit tests
    └── cli.test.ts      # Integration tests
```

## Content Format

Create Markdown files in your content directory with YAML frontmatter:

```markdown
---
title: My Post Title
date: 2024-01-15
tags:
  - typescript
  - testing
---

# Content

Your markdown content here...
```

## Output

The generator creates:
- Individual HTML files for each post (e.g., `my-post.html`)
- `index.html` with links to all pages, sorted by date (newest first)

## Testing

```bash
npm test
```

All tests pass successfully with comprehensive coverage for:
- Markdown parsing and frontmatter extraction
- HTML generation with proper escaping
- Index generation with sorting
- CLI integration and directory handling
