# ssg

A small static site generator that turns Markdown files into HTML pages.

```sh
npm install
npm run build
npx ssg build
```

Markdown is read from `./content` and HTML is written to `./dist`. Override those directories when needed:

```sh
npx ssg build --content posts --output public
```

Use incremental builds to skip pages whose Markdown source and templates have not
changed. The output directory stores rendered HTML and a `.ssg-cache.json`
manifest containing source hashes and cached frontmatter. A missing manifest or
`--clean` starts with a clean build:

```sh
npx ssg build --incremental
npx ssg build --incremental --clean
```

Each build reports pages built, pages skipped, elapsed time, and estimated time
saved by cached pages.

Start a development server on `http://localhost:3000` with automatic rebuilds and
browser reloads when files in `content/` or `templates/` change:

```sh
npx ssg serve
npx ssg serve --port 4000
```

Templates are read from `./templates` (or set with `--templates`). A page can select a
Handlebars template and layout in its frontmatter:

```md
---
title: Hello
template: post
layout: site
---
```

`templates/default.hbs` is used when `template` is omitted. Layouts belong in
`templates/layouts` and insert rendered page content with `{{{body}}}`. Reusable
partials belong in `templates/partials` and can be included with `{{> header}}`.
Templates support escaped `{{value}}`, raw `{{{value}}}`, `{{#if value}}`, and
`{{#each values}}` expressions.

Frontmatter supports `title`, `date`, and either array or comma-separated `tags`:

```md
---
title: Hello
date: 2026-08-13
tags: [news, updates]
---

# Welcome
```

## Plugins

Add TypeScript plugin modules to `plugins/` and list them in `ssg.config.ts`:

```ts
// plugins/example.ts
import type { Plugin } from 'ssg';

export const examplePlugin: Plugin = {
  name: 'example',
  onFile(page) {
    page.html += '<footer>Built with ssg</footer>';
  },
};
```

```ts
// ssg.config.ts
import { defineConfig } from 'ssg';
import { examplePlugin } from './plugins/example';

export default defineConfig({
  plugins: [examplePlugin],
});
```

Plugins can implement `onStart`, `beforeBuild`, `onFile`, `afterBuild`, and
`onEnd`. Each lifecycle stage runs in configured order. Markdown parsing,
Handlebars templates, and the development server are exposed as the built-in
`MarkdownPlugin`, `TemplatePlugin`, and `DevServerPlugin` classes.
