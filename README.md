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

## Templates

Put Handlebars templates in `./templates`, layouts in `./templates/layouts`, and reusable partials in `./templates/partials`. Pages use `default.hbs` and the `layouts/default.hbs` layout unless frontmatter selects another file:

```yaml
---
title: My post
template: post
layout: site
---
```

Page templates receive frontmatter plus `title`, `date`, `tags`, `url`, and raw Markdown HTML as `content`. Layouts additionally receive the rendered page as `body`. Use triple braces for HTML and partial syntax for includes:

```handlebars
{{> header}}
<main>{{{body}}}</main>
{{> footer}}
```

Override the template directory with `npx ssg build --templates ./theme`. If no template directory exists, the built-in page renderer remains in use.

## Plugins

Add TypeScript plugin modules under `./plugins/` and load them from `ssg.config.ts`:

```ts
import type { Plugin } from 'ssg';

const example: Plugin = {
  name: 'example',
  onFile(page) {
    page.data = { ...page.data, generated: true };
  },
};

export default { plugins: [example] };
```

Plugins can implement `onStart`, `beforeBuild`, `onFile`, `afterBuild`, and `onEnd`. Hooks may be synchronous or asynchronous and run in configuration order. `onFile` receives each parsed page and may mutate it or return a replacement. Markdown parsing and template rendering are built-in plugins around configured plugins; the development server is exposed as `DevServerPlugin` and through the compatible `startDevServer` API.

## Development server

Build and serve `./dist` at `http://localhost:3000` with:

```sh
npx ssg serve
```

Changes under `content/` or `templates/` rebuild the site and reload connected browsers. Use `--port <number>` to select another port. The `--content`, `--output`, and `--templates` options are also supported by `serve`.

Run tests with `npm test`.
