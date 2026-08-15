# Static Site Generator (SSG)

A command-line static site generator built in TypeScript that converts Markdown files with YAML frontmatter into a complete HTML site.

## Features

- **Markdown Support**: Renders Markdown to HTML using `marked`
- **YAML Frontmatter**: Parse page metadata (title, date, tags) from YAML frontmatter blocks
- **Automatic Index**: Generates an index.html listing all pages
- **Responsive HTML**: Each page includes proper HTML structure with charset, viewport, and semantic elements
- **Back Navigation**: Each page includes a link back to the home page
- **Metadata Rendering**: Displays title, date, and tags on each page
- **TypeScript**: Fully typed with strict mode enabled
- **Comprehensive Tests**: Jest test suite covering CLI, frontmatter parsing, and site generation

## Installation

```bash
npm install
npm run build
```

## Usage

### Basic Build

```bash
npx ssg build
```

This builds your site from `./content` directory to `./dist` directory.

### Custom Directories

```bash
npx ssg build --content ./src/pages --output ./public
```

### Options

- `--content <dir>`: Content directory (default: `./content`)
- `--output <dir>`: Output directory (default: `./dist`)
- `--help`: Show help message

## Project Structure

```
.
├── src/
│   ├── index.ts           # CLI entry point
│   ├── cli.ts             # Argument parser
│   ├── frontmatter.ts     # YAML frontmatter parser
│   ├── ssg.ts             # Core SSG logic
│   └── __tests__/         # Jest test suite
├── content/               # Source markdown files
├── dist/                  # Generated HTML files
├── package.json
├── tsconfig.json
└── jest.config.js
```

## Content Format

Create `.md` files in the `content/` directory with YAML frontmatter:

```markdown
---
title: My Blog Post
date: 2024-08-15
tags: [javascript, typescript]
---

# My Blog Post

This is the markdown content. You can use:

- **Bold** and *italic*
- [Links](https://example.com)
- Code blocks
- Lists
- Headers
- And all standard markdown features

## Subsection

More content here...
```

## Development

### Build TypeScript

```bash
npm run build
```

### Run Tests

```bash
npm test
```

### Clean Build

```bash
npm run clean
```

## Test Coverage

The project includes comprehensive test suites for:

- **CLI Parser** (`cli.test.ts`): Argument parsing, default values, option handling
- **Frontmatter Parser** (`frontmatter.test.ts`): YAML parsing, boolean/numeric values, arrays
- **SSG Engine** (`ssg.test.ts`): File generation, HTML structure, markdown rendering, metadata inclusion

## Generated HTML

Each generated page includes:

- Proper HTML5 document structure
- Charset and viewport meta tags
- Title from frontmatter
- Date meta tag (if provided)
- Tags meta tag (if provided)
- Back link to home
- Rendered markdown content
- Visual display of metadata

The generated `index.html` provides an overview of all pages with:

- Links to each generated page
- Page titles
- Publication dates (if available)

## Technical Details

- **Parser**: Uses `marked` for markdown to HTML conversion
- **Frontmatter**: Manual YAML parser for `---`-delimited blocks (gray-matter compatibility layer)
- **Runtime**: TypeScript compiled to ES2020 JavaScript
- **Tests**: Jest with ts-jest preset
- **Strict Mode**: All TypeScript strict mode checks enabled

## License

ISC
