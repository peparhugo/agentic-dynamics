# TypeScript Static Site Generator

Build a site from Markdown files with YAML frontmatter:

```sh
npm install
npm run build
npx ssg build
```

The default input directory is `./content`, the template directory is `./templates`,
and the default output directory is `./dist`.
Override them with:

```sh
npx ssg build --content posts --output public --templates theme
```

Use `npx ssg build --incremental` to reuse unchanged rendered pages. Source and
template hashes, parsed page data, rendered HTML, and timing data are stored in
`.ssg-cache.json` beside the content directory. `--clean` discards output and performs
a full build. Incremental builds report pages built, pages skipped, and estimated time
saved.

## Development server

Build and serve the site with live reload at `http://localhost:3000`:

```sh
npx ssg serve
```

The server watches `content/` and `templates/`, rebuilds after changes, and reloads
connected browsers. Use another port with `npx ssg serve --port 4000`. The build path
options are also available to the `serve` command.

Supported frontmatter fields include `title`, `date`, `tags`, `template`, and `layout`.
Any additional fields are available as template variables. ISO dates are parsed as
strings and displayed in a readable UTC format. Raw HTML embedded in Markdown is
explicitly unescaped after Markdown rendering.

## Templates

Templates use Handlebars and the following structure:

```text
templates/
  default.hbs
  layouts/
    default.hbs
  partials/
    header.hbs
    footer.hbs
    nav.hbs
```

`default.hbs` is used when a page does not set `template` in its frontmatter. Page
templates receive the rendered Markdown as `{{{content}}}`. If present,
`layouts/default.hbs` wraps the result and receives it as `{{{body}}}`. Select another
layout with `layout: name`, or disable layouts with `layout: false`. Include reusable
partials with standard Handlebars syntax such as `{{> header}}`.

When `templates/default.hbs` is absent, pages retain the generator's built-in HTML
output for compatibility.

## Plugins

Add TypeScript plugin modules under `plugins/` and list them in `ssg.config.ts`:

```ts
import type { Plugin, SsgConfig } from './src/index';
import myPlugin from './plugins/my-plugin';

const config: SsgConfig = { plugins: [myPlugin] };
export default config;
```

A plugin can implement `onStart`, `beforeBuild`, `onFile(page)`, `afterBuild`, and
`onEnd`. Hooks run in configuration order. Markdown parsing and template rendering
are built-in plugins around configured file hooks; the development server and live
reload are provided by `DevServerPlugin` while the existing `startDevServer` API
remains available.
