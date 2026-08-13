# ssg

A TypeScript CLI that converts Markdown files with YAML frontmatter into a static HTML site.

```sh
npm install
npm run build
npx ssg build
```

By default, Markdown is read recursively from `./content` and HTML is written to `./dist`. Use custom directories with:

```sh
npx ssg build --content ./posts --output ./public
```

Supported frontmatter fields are `title`, `date`, `tags`, `template`, and `layout`. Every Markdown file gets a matching `.html` path and the generator creates an `index.html` containing links to all pages.

Handlebars templates can be placed in `./templates`. A page uses `default.hbs` unless its frontmatter selects another template. Templates receive all frontmatter fields plus `title`, `date`, `tags`, `url`, and the rendered Markdown as `content`; use triple braces (`{{{content}}}`) to preserve its HTML.

Layouts live in `./templates/layouts`, default to `default.hbs`, and insert the rendered page template with `{{{body}}}`. Reusable partials live in `./templates/partials` and can be included by filename, for example `{{> header}}`. Variables written as `{{title}}` are HTML escaped.

Use a different template directory with:

```sh
npx ssg build --templates ./theme/templates
```

For local development, build and serve `./dist` with live reload:

```sh
npx ssg serve
npx ssg serve --port 4000
```

The development server watches the content and template directories, rebuilds when files change, and reloads connected browsers after a successful build. It accepts the same `--content`, `--output`, and `--templates` options as `build`.

## Plugins

Add TypeScript plugins in `./plugins` and load them from `ssg.config.ts`:

```ts
import type { SsgConfig } from 'ssg';
import example from './plugins/example';

export default {
  plugins: [example],
} satisfies SsgConfig;
```

A plugin can implement `onStart`, `beforeBuild`, `onFile`, `afterBuild`, and `onEnd`. Each lifecycle hook runs in plugin order. `onFile(page, context)` can update a parsed page before it is rendered. Markdown parsing, Handlebars rendering, and the development server use the same plugin lifecycle internally.
