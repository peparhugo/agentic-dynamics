# ssg

A small TypeScript CLI that turns Markdown files with optional YAML frontmatter into a static HTML site.

```yaml
---
title: Example post
date: 2025-02-03
tags: [news, typescript]
---

# Hello
```

## Usage

```sh
npm install
npm run build
npx ssg build
npx ssg build --content ./posts --output ./public
npx ssg build --templates ./templates
npx ssg build --incremental
npx ssg build --incremental --clean
npx ssg serve
npx ssg serve --port 4000
```

Markdown files are discovered recursively. Their relative paths are preserved with an `.html` extension, and an `index.html` containing links to every page is generated in the output directory.

Incremental builds store source hashes, template hashes, parsed frontmatter, and rendered HTML in `<output>/.ssg-cache.json`. Unchanged pages are skipped, while source or template changes invalidate their cached output. A missing cache or `--clean` performs a clean build. Build output reports pages built, pages skipped, and estimated render time saved.

`ssg serve` builds into `./dist`, serves it at `http://localhost:3000`, and reloads connected browsers after changes under `content/` or `templates/`. The build directory and watched directories can also be changed with the same options accepted by `build`.

## Templates

Handlebars templates use this structure:

```text
templates/
  default.hbs
  post.hbs
  layouts/
    base.hbs
  partials/
    header.hbs
```

`default.hbs` is used when a page does not select a template. Select templates and layouts in frontmatter:

```yaml
---
title: Example
template: post
layout: base
---
```

Templates receive frontmatter plus `title`, `date`, `tags`, `url`, and the rendered Markdown as `{{{content}}}`. Layouts receive the rendered page as `{{{body}}}`. Files under `partials/` are available by relative name, such as `{{> header}}`.

## Plugins

Add TypeScript plugin modules under `plugins/` and load them from `ssg.config.ts`:

```ts
import type { Plugin, SsgConfig } from 'ssg';
import myPlugin from './plugins/my-plugin';

export default { plugins: [myPlugin] } satisfies SsgConfig;
```

A plugin can implement `onStart(context)`, `beforeBuild(context)`, `onFile(page, context)`, `afterBuild(context)`, and `onEnd(context)`. Hooks run in configuration order. The built-in Markdown plugin runs before configured `onFile` hooks, and the built-in template plugin runs after them.
