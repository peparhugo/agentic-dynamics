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
