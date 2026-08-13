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
npx ssg build --templates ./templates
npx ssg build --incremental
npx ssg build --incremental --clean
npx ssg serve
npx ssg serve --port 4000
```

Markdown files are read recursively. Each becomes an HTML file at the matching relative path, and an `index.html` links to every generated page.

Incremental builds store source and template hashes plus rendered page data in `dist/.ssg-cache.json`. Unchanged pages are skipped, template or partial changes invalidate rendered pages, and `--clean` removes prior output before rebuilding. The CLI reports pages built, pages skipped, and estimated time saved.

`ssg serve` builds into `./dist`, serves it on `http://localhost:3000`, and watches `content/` and `templates/`. Successful rebuilds automatically reload connected browsers. The build directories and port can be changed with the same directory options as `build` and with `--port`.

## Templates

Handlebars templates live in `templates/`. A page can select a template and layout in its frontmatter:

```yaml
---
title: Example post
template: post
layout: main
---
```

`templates/default.hbs` is used when `template` is omitted. Layouts live in `templates/layouts/` and insert the rendered page with `{{{body}}}`; `layouts/default.hbs` is used when `layout` is omitted. Reusable partials live in `templates/partials/` and can be included with `{{> header}}`. Templates receive all frontmatter fields plus normalized `title`, `date`, `tags`, `outputPath`, and rendered Markdown as `content` and `body`.

## Plugins

Add TypeScript plugins in `plugins/` and load them from `ssg.config.ts`:

```ts
import { defineConfig, type Plugin } from 'flat-file-ssg';
import addFooter from './plugins/add-footer';

export default defineConfig({
  plugins: [addFooter]
});
```

A plugin can implement `onStart`, `beforeBuild`, `onFile`, `afterBuild`, and `onEnd`. Hooks run in plugin order and may be asynchronous. `onFile(page, context)` can inspect or modify each page, including its rendered `html`. Markdown parsing, Handlebars templates, and the live-reload development server use the same plugin pipeline as project plugins.
