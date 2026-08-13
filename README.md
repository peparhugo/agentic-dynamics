# ssg

A small TypeScript static site generator for Markdown files with YAML frontmatter.

```sh
npm install
npm run build
npx ssg build
```

The command reads `./content` and writes the generated site to `./dist`. Use custom paths with:

```sh
npx ssg build --content posts --output public
```

Templates are loaded from `./templates` by default. Pass `--templates <dir>` to use
a different directory. Pages may select a Handlebars template and layout in their
frontmatter:

```md
---
title: First post
template: post
layout: site
---
```

`template: post` loads `templates/post.hbs`, and `layout: site` loads
`templates/layouts/site.hbs`. If omitted, `default.hbs` files are used when
present. Layouts insert rendered page content with `{{{body}}}`. Reusable files
in `templates/partials` can be included by name, for example `{{> header}}`.
Template values such as `{{title}}` are HTML escaped; rendered Markdown is
available as `{{{content}}}`. Set `layout: false` to render without a layout.

Start a development server at `http://localhost:3000` with:

```sh
npx ssg serve
```

The server builds into `./dist`, watches `content/` and `templates/`, and reloads
open browser pages after successful rebuilds. Use `--port <number>` to select a
different port. The `--content`, `--output`, and `--templates` options work for
both `build` and `serve`.

Frontmatter can define `title`, `date`, and `tags`:

```md
---
title: First post
date: 2026-08-13
tags: [news, example]
---

# Hello
```

## Plugins

Add TypeScript plugin modules under `plugins/` and load them from `ssg.config.ts`:

```ts
import { defineConfig, type Plugin } from 'ssg';
import audit from './plugins/audit';

export default defineConfig({ plugins: [audit] });
```

Plugins may implement `onStart`, `beforeBuild`, `onFile`, `afterBuild`, and `onEnd`.
Hooks run in configuration order. `onFile(page, context)` can inspect or change each
page after the built-in Markdown plugin and before the built-in template plugin.
`MarkdownPlugin`, `TemplatePlugin`, and `DevServerPlugin` are also exported for
custom engine pipelines.
