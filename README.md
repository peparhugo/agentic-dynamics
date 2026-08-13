# ssg

A small static site generator that turns Markdown files into HTML.

## Usage

```sh
npm install
npm run build
npx ssg build
npx ssg build --incremental
```

Incremental builds store source and template hashes in `.ssg-cache.json`. Pages
whose Markdown and templates are unchanged are not parsed, processed by file
plugins, or rendered again. Use `--clean` to discard the manifest and output
before rebuilding, or `--cache <file>` to choose a different manifest path.
The CLI reports built and skipped page counts and estimated
time saved after each incremental build.

For development, build and serve the site with live reload. Changes under
`content` or `templates` trigger a rebuild and refresh connected browsers:

```sh
npx ssg serve
npx ssg serve --port 4000
```

By default, Markdown is read from `./content`, Handlebars templates from
`./templates`, and HTML is written to `./dist`. Use the directory options to
select different locations:

```sh
npx ssg build --content posts --output public --templates theme
```

Markdown files can include YAML frontmatter:

```markdown
---
title: Hello
date: 2026-08-13
tags: [news, example]
---

# Hello
```

## Templates

Put page templates in `templates`, layouts in `templates/layouts`, and reusable
partials in `templates/partials`. A page can select both a template and layout:

```markdown
---
title: Hello
template: post
layout: site
---

Hello **world**.
```

`templates/post.hbs` receives all frontmatter plus `title`, `date`, `tags`,
`url`, and rendered Markdown as `content`:

```hbs
{{> header}}
<article><h1>{{title}}</h1>{{{content}}}</article>
{{> footer}}
```

Use `{{{body}}}` where page output belongs in `templates/layouts/site.hbs`.
When frontmatter omits `template` or `layout`, `default.hbs` is used when that
file exists. Without templates, the original built-in page output is retained.

## Plugins

Add TypeScript plugins under `plugins` and load them from `ssg.config.ts`:

```ts
import type { SsgConfig } from 'ssg';
import analytics from './plugins/analytics';

export default {
  plugins: [analytics]
} satisfies SsgConfig;
```

A plugin can implement any lifecycle hook. Hooks run in plugin order; `onFile`
runs once for each parsed page:

```ts
import type { Plugin } from 'ssg';

const analytics: Plugin = {
  name: 'analytics',
  onStart(context) {},
  beforeBuild(context) {},
  onFile(page, context) {},
  afterBuild(context) {},
  onEnd(context) {}
};

export default analytics;
```

`MarkdownPlugin`, `TemplatePlugin`, and `DevServerPlugin` provide the built-in
Markdown, rendering, and live-reload behavior. `buildSite` also accepts a
`plugins` array directly for programmatic use.
