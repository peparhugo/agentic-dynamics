# TypeScript Static Site Generator

Build a site from Markdown files with YAML frontmatter:

```sh
npm install
npm run build
npx ssg build
```

The default input directory is `./content` and the default output directory is `./dist`.
Override them with:

```sh
npx ssg build --content posts --output public
```

Supported frontmatter fields are `title`, `date`, and `tags`. ISO dates are parsed as
strings and displayed in a readable UTC format. Raw HTML embedded in Markdown is
explicitly unescaped after Markdown rendering.
