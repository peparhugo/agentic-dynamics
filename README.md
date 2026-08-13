# Static Site Generator (SSG)

A fast and simple static site generator CLI built in TypeScript. Convert Markdown files with YAML frontmatter into a complete static HTML site.

## Features

- **Markdown to HTML**: Convert Markdown files to clean HTML using the `marked` library
- **YAML Frontmatter**: Parse frontmatter for title, date, and tags using a custom YAML parser
- **Automatic Index**: Generate an index page that lists all posts sorted by date
- **CLI Interface**: Simple command-line interface with customizable content and output directories
- **HTML Generation**: Each Markdown file becomes its own HTML page
- **Type Safe**: Built with TypeScript strict mode for reliability

## Installation

```bash
npm install
npm run build
```

## Usage

### Basic Usage

```bash
npm run build  # Compile TypeScript
node dist/cli.js build
```

This will:
1. Read all `.md` files from `./content` (default)
2. Parse frontmatter and convert Markdown to HTML
3. Generate individual HTML pages in `./dist` (default)
4. Generate an `index.html` listing all pages

### Custom Directories

```bash
node dist/cli.js build --content ./my-posts --output ./public
```

### Options

- `--content <dir>`: Content directory containing Markdown files (default: `./content`)
- `--output <dir>`: Output directory for generated HTML (default: `./dist`)

## Frontmatter Format

Each Markdown file should start with YAML frontmatter:

```markdown
---
title: My Article Title
date: 2023-01-15
tags: [javascript, typescript, testing]
---

# Article Content

Your markdown content goes here...
```

Supported frontmatter fields:
- `title`: Page title (required for nice display)
- `date`: Publication date in ISO format (used for sorting)
- `tags`: Array of tags for categorization

## Project Structure

```
src/
├── cli.ts           # CLI entry point
├── generator.ts     # Site generation logic
├── frontmatter.ts   # YAML frontmatter parser
├── markdown.ts      # Markdown to HTML conversion
├── index.ts         # Public API exports
└── *.test.ts        # Jest tests
dist/               # Compiled JavaScript output
```

## Testing

```bash
npm test
npm run test:watch  # Run tests in watch mode
```

## Example

### Input (content/hello.md)

```markdown
---
title: Hello World
date: 2023-12-01
tags: [welcome, demo]
---

# Welcome

This is my first post!

- Feature 1
- Feature 2
```

### Output (dist/hello.html)

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <title>Hello World</title>
  <!-- ... -->
</head>
<body>
  <h1>Hello World</h1>
  <p class="date">2023-12-01</p>
  <div class="tags">
    <span class="tag">welcome</span>
    <span class="tag">demo</span>
  </div>
  <h1>Welcome</h1>
  <p>This is my first post!</p>
  <ul>
    <li>Feature 1</li>
    <li>Feature 2</li>
  </ul>
</body>
</html>
```

## Implementation Details

### Custom YAML Parser

The project includes a custom YAML parser instead of using gray-matter. It handles:
- String values (quoted and unquoted)
- Boolean values (`true`, `false`)
- Numeric values (integers and floats)
- Arrays (`[item1, item2]`)
- Null values (`null`)
- Comments (lines starting with `#`)

### HTML Generation

- Each page includes navigation links back to the index
- Date and tags are displayed if present in frontmatter
- HTML is properly escaped to prevent XSS vulnerabilities
- Generated index sorts posts by date in descending order

## Development

```bash
npm run build    # Compile TypeScript
npm test         # Run tests
npm run clean    # Remove compiled output
```

## License

MIT
