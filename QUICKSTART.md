# Quick Start Guide

## Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Build TypeScript:**
   ```bash
   npm run build
   ```

3. **Run tests:**
   ```bash
   npm test
   ```

## Build Your Site

```bash
npx ssg build
```

This generates HTML files from markdown in the `./content` directory and outputs them to `./dist`.

## Custom Directories

```bash
npx ssg build --content ./pages --output ./public
```

## Example Content

Create a markdown file in `content/` like this:

**content/my-post.md:**
```markdown
---
title: My First Post
date: 2024-08-15
tags: [blog, introduction]
---

# Welcome

This is my first post using the static site generator!

## Features

- Markdown support
- YAML frontmatter
- Automatic HTML generation
- Index page with links to all posts

Check out the [example files](./content/) in the content directory!
```

## File Structure After Build

```
dist/
├── index.html          # Home page with list of posts
├── my-post.html        # Generated from my-post.md
└── ...                 # More generated pages
```

## Deploy

The entire `dist/` directory is your complete static website. Deploy it to:

- GitHub Pages
- Netlify
- Vercel
- Any web server
- S3 bucket
- Or any static hosting service

## Examples

The project includes two example posts:
- `content/hello-world.md` - Welcome post with examples
- `content/getting-started.md` - Setup guide

## Test Everything

```bash
# Compile TypeScript
npm run build

# Run all tests
npm test

# Clean build artifacts
npm run clean
```

## Troubleshooting

If the build fails:
1. Ensure all markdown files are in the `content/` directory
2. Check frontmatter format (must start and end with `---`)
3. Verify no other files end with `.md` in content directory
4. Check that markdown syntax is valid

## Need Help?

See [README.md](./README.md) for complete documentation.
