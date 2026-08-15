# ssg

A small static site generator for Markdown files.

```sh
npm install
npm run build
npx ssg build
```

By default, Markdown is read recursively from `./content` and HTML is written to `./dist`.

```sh
npx ssg build --content ./posts --output ./public
```

Reuse unchanged page output with an incremental build:

```sh
npx ssg build --incremental
npx ssg build --incremental --clean
```

Incremental builds store source hashes, parsed frontmatter, and rendered HTML in
`<output>/.ssg-cache.json`. A missing cache or `--clean` performs a clean build.
The build summary reports pages built, pages skipped, and estimated time saved.

Start a development server at `http://localhost:3000` with live reload:

```sh
npx ssg serve
npx ssg serve --port 4000
```

The development server builds and serves `./dist`, watches `./content` and
`./templates`, then reloads connected browsers after each successful rebuild.
The `--content`, `--output`, and `--templates` options are also supported by
`serve`.

Templates are loaded from `./templates` by default. Use `--templates <dir>` to
choose another directory. Pages use `templates/default.hbs`, or can select a
template and layout in frontmatter:

```markdown
---
title: Hello
template: post
layout: main
---
```

Page templates receive the frontmatter fields plus `title`, `url`, `content`,
`html`, `page`, and `pages`. Markdown HTML should use an unescaped expression,
such as `{{{content}}}`. Layouts live in `templates/layouts` and insert the page
template with `{{{body}}}`. Partials live in `templates/partials` and can be
included with `{{> header}}`; nested partial names use forward slashes.

Pages may start with YAML frontmatter:

```markdown
---
title: Hello
date: 2026-08-16
tags: [news, release]
---

# Welcome
```

## Plugins

Add TypeScript plugins in `plugins/` and list them in `ssg.config.ts`. Hooks run
in declaration order and may be synchronous or asynchronous:

```ts
import type { Plugin, SsgConfig } from './src';

const labels: Plugin = {
  name: 'labels',
  onFile(page) {
    page.data.label = `Page: ${page.title}`;
  },
};

export default {
  plugins: [labels],
} satisfies SsgConfig;
```

The lifecycle is `onStart`, `beforeBuild`, `onFile` for every page,
`afterBuild`, and `onEnd`. `MarkdownPlugin`, `TemplatePlugin`, and
`DevServerPlugin` are exported for custom integrations. The normal build API
installs Markdown and template handling automatically; configured plugins run
after those built-ins, with generated files written during `afterBuild`. During
an incremental build, `onFile` runs only for pages invalidated by source or
template changes; the other lifecycle hooks continue to run for every build.
