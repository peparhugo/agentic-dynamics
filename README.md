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
