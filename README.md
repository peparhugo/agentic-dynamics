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

Supported frontmatter fields are `title`, `date`, and `tags`. Every Markdown file gets a matching `.html` path and the generator creates an `index.html` containing links to all pages.
