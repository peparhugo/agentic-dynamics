# ssg

A small TypeScript static site generator backed entirely by Markdown files.

## Usage

```sh
npm install
npm run build
npx ssg build
npx ssg build --content ./posts --output ./public
npx ssg build --templates ./templates
npx ssg serve
npx ssg serve --port 4000
```

`ssg serve` builds into `./dist`, serves it at `http://localhost:3000`, and
reloads open pages whenever files under `content/` or `templates/` change.
The build directory and watched directories can also be changed with the same
options accepted by `ssg build`.

Markdown files may include `title`, `date`, and `tags` frontmatter:

```markdown
---
title: Example page
date: 2024-05-01
tags: [example, news]
---

# Page content
```

## Templates

Handlebars templates live in `templates/`. A page may select one with `template`
frontmatter; otherwise `templates/default.hbs` is used when present. Templates
receive all frontmatter fields and the rendered Markdown as both `content` and
`body`.

```markdown
---
title: About
template: page
layout: default
---
```

Layouts live in `templates/layouts/` and must use `{{{body}}}` for rendered page
content. `templates/layouts/default.hbs` is applied by default when present.
Reusable partials live in `templates/partials/` and can be included by filename,
for example `{{> header}}`. Set `template: false` or `layout: false` to skip a
default template or layout for a page. Without template files, the original
built-in page output remains unchanged.

## Plugins

Add TypeScript plugins to `plugins/` and load them from `ssg.config.ts`. Hooks run
in plugin order for every lifecycle stage. Configured `onFile` hooks run after
Markdown parsing and before template rendering, so they can inspect or change a
page's frontmatter, rendered Markdown, metadata, or output paths.

```ts
// ssg.config.ts
import type { SsgConfig } from './src/generator';
import readingTime from './plugins/reading-time';

export default { plugins: [readingTime] } satisfies SsgConfig;
```

Plugins may implement `onStart(context)`, `beforeBuild(context)`,
`onFile(page)`, `afterBuild(context)`, and `onEnd(context)`. Hooks may be sync
or async. The built-in `MarkdownPlugin`, `TemplatePlugin`, and
`DevServerPlugin` use the same interface.
