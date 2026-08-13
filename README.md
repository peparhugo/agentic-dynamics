# ssg

A strict TypeScript CLI that turns Markdown files into a static HTML site. Frontmatter supports `title`, `date`, `tags`, `template`, and `layout`.

## Usage

```sh
npm install
npm run build
npx ssg build
npx ssg serve
```

The default input directory is `./content` and the default output directory is `./dist`.

```sh
npx ssg build --content ./posts --output ./public
```

Templates are Handlebars files under `./templates`. Use `default.hbs` as the default page template, `layouts/default.hbs` as the default layout, and reusable partials from `partials/*.hbs`. The rendered Markdown is available as `{{{content}}}` in page templates, and rendered page output is available as `{{{body}}}` in layouts.

```yaml
---
title: About
template: page
layout: main
---
```

Template and layout names may include or omit `.hbs`. Select another template directory with `--templates <dir>`. Set `layout: false` to skip a default layout.

Markdown files in nested directories retain their relative paths. Every page is linked from the generated `index.html`.

## Plugins

Add TypeScript plugin modules under `plugins/` and load them from `ssg.config.ts`. Hooks run in configuration order and may be synchronous or asynchronous. `onFile` receives a mutable page after the built-in Markdown and template plugins have rendered it.

```ts
// plugins/footer.ts
import type { Plugin } from 'ssg';

const footer: Plugin = {
  name: 'footer',
  onFile(page) {
    page.html += '<footer>Built with ssg</footer>';
  },
};

export default footer;
```

```ts
// ssg.config.ts
import { defineConfig } from 'ssg';
import footer from './plugins/footer';

export default defineConfig({ plugins: [footer] });
```

Plugins support `onStart(context)`, `beforeBuild(context)`, `onFile(page)`, `afterBuild(context)`, and `onEnd(context)`. Markdown parsing, Handlebars rendering, and the development server are available as the built-in `MarkdownPlugin`, `TemplatePlugin`, and `DevServerPlugin` classes.

## Development server

`npx ssg serve` builds the site, serves `./dist` at `http://localhost:3000`, and watches `content/` and `templates/`. A successful rebuild automatically reloads connected browser pages. Select another port or use the same directory options accepted by `build`:

```sh
npx ssg serve --port 4000 --content ./posts --templates ./views --output ./public
```

This tool has no HTTP API or REST endpoints. It only reads local Markdown and writes static files, so no network API protocol is involved.
