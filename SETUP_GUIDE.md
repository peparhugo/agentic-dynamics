# Setup and Running Guide

## Prerequisites

- Node.js 18+ (with npm)
- A terminal/command line

## Installation Steps

1. **Install dependencies:**
   ```bash
   npm install
   ```

   This will install:
   - `typescript` - TypeScript compiler
   - `marked` - Markdown to HTML parser
   - `gray-matter` - Frontmatter YAML parser
   - `jest` - Testing framework
   - `ts-jest` - TypeScript support for Jest

2. **Build the project:**
   ```bash
   npm run build
   ```

   This compiles TypeScript files from `src/` to JavaScript in `dist/`.

## Running Tests

Execute all tests:
```bash
npm test
```

This runs Jest and executes:
- **Parser tests** - Verify markdown parsing and frontmatter extraction
- **Generator tests** - Verify HTML generation and escaping
- **Integration tests** - Verify CLI functionality

## Using the CLI

### Option 1: Using default directories

```bash
# Creates content in ./content and output to ./dist
npx ssg build
```

### Option 2: Custom directories

```bash
# Custom input and output directories
npx ssg build --content ./my-posts --output ./my-site

# Only custom content directory
npx ssg build --content ./posts

# Only custom output directory
npx ssg build --output ./website
```

## Project Structure

```
.
├── src/
│   ├── cli.ts                 # CLI entry point and argument parsing
│   ├── parser.ts              # Markdown parser with gray-matter
│   ├── generator.ts           # HTML generation functions
│   └── __tests__/
│       ├── parser.test.ts     # Parser unit tests
│       ├── generator.test.ts  # Generator unit tests
│       └── cli.test.ts        # Integration tests
├── dist/                       # Compiled JavaScript (generated)
├── content/                    # Sample markdown files
├── package.json               # Project configuration
├── tsconfig.json              # TypeScript configuration
├── jest.config.js             # Jest configuration
└── README.md                  # Main documentation
```

## Example Workflow

1. **Create content directory:**
   ```bash
   mkdir my-content
   ```

2. **Add markdown files:**
   ```bash
   cat > my-content/hello.md << 'EOF'
   ---
   title: Hello World
   date: 2024-01-15
   tags:
     - hello
   ---

   # Hello World

   This is my first post!
   EOF
   ```

3. **Build the site:**
   ```bash
   npm run build
   npx ssg build --content my-content --output my-output
   ```

4. **Check results:**
   ```bash
   ls my-output/
   # Output: hello.html  index.html
   ```

5. **View in browser:**
   Open `my-output/index.html` in your browser to see the site.

## Testing Locally

To run the full test suite:

```bash
npm test
```

Expected output:
```
PASS  src/__tests__/parser.test.ts
PASS  src/__tests__/generator.test.ts
PASS  src/__tests__/cli.test.ts

Test Suites: 3 passed, 3 total
Tests:       22 passed, 22 total
Snapshots:   0 total
Time:        3.456s
```

## Troubleshooting

### "ssg: command not found"
Make sure you've built the project:
```bash
npm run build
```

### "Content directory not found"
The specified content directory doesn't exist. Create it:
```bash
mkdir -p ./your-content-dir
```

### Markdown not rendering
Ensure your markdown files have `.md` extension and are in the correct directory.

### Test failures
1. Clear node_modules and rebuild:
   ```bash
   rm -rf node_modules
   npm install
   npm run build
   npm test
   ```

## Development Mode

For continuous compilation during development:
```bash
npm run dev
```

This starts TypeScript compiler in watch mode.

## Deployment

To deploy the generated site:

1. Build the site (creates `./dist` directory)
2. Upload contents of `dist/` to your web server
3. The site is fully static HTML - no server-side processing needed

The output is optimized for:
- GitHub Pages
- Netlify
- Vercel
- Any static hosting service
- Traditional web servers
