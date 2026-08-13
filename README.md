# ssg

A strict TypeScript CLI that turns Markdown files into a static HTML site. Frontmatter supports `title`, `date`, and `tags`.

## Usage

```sh
npm install
npm run build
npx ssg build
```

The default input directory is `./content` and the default output directory is `./dist`.

```sh
npx ssg build --content ./posts --output ./public
```

Markdown files in nested directories retain their relative paths. Every page is linked from the generated `index.html`.

This tool has no HTTP API or REST endpoints. It only reads local Markdown and writes static files, so no network API protocol is involved.
