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
npx ssg serve
npx ssg serve --port 4000
```

Markdown files are read recursively. Each becomes an HTML file at the matching relative path, and an `index.html` links to every generated page.

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
