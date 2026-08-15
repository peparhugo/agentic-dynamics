# Live-Reload Development Server Implementation

## Overview
A complete live-reload dev server has been added to the SSG, enabling real-time updates during development.

## Features Implemented

### 1. Development Server (`src/serve.ts`)
- HTTP server serving static files from the `./dist` directory
- WebSocket server for live-reload notifications
- Automatic WebSocket script injection into HTML files
- File watching on `content/` and `templates/` directories
- Automatic rebuild on file changes with debouncing
- Configurable port (default: 3000)
- Proper server shutdown handling

### 2. CLI Updates (`src/cli.ts`)
- New `serve` command added to CLI argument parser
- `--port` option for custom port configuration
- Full backward compatibility with existing `build` command
- Port validation and parsing

### 3. Entry Point Updates (`src/index.ts`)
- Routing for `serve` command to the serve module
- Error handling for serve command failures
- Process remains running to keep dev server alive

### 4. Live Reload Mechanism
The implementation uses:
- **Chokidar**: Watches file system for changes with stabilization
- **WebSocket (ws)**: Two-way communication for live reload triggers
- **Script Injection**: Embeds a WebSocket client in served HTML pages

### 5. Test Coverage (`src/serve.test.ts`, updated `src/cli.test.ts`)

#### CLI Tests
- Parsing `serve` command
- Parsing `--port` option with numeric values
- Combining serve with other options (--content, --output)
- Default port behavior

#### Server Tests
- File serving from output directory
- Live reload script injection into HTML
- 404 handling for non-existent files
- Index.html serving for directory requests

## Usage

### Start Development Server
```bash
npx ssg serve
```

### Custom Port
```bash
npx ssg serve --port 8000
```

### With Custom Directories
```bash
npx ssg serve --content ./pages --output ./public --port 5000
```

## How It Works

1. **Initial Rebuild**: When the server starts, it builds the site
2. **File Watching**: Chokidar monitors `content/` and `templates/` directories
3. **Change Detection**: Any file change triggers a rebuild
4. **WebSocket Notification**: After rebuild completes, all connected clients are notified
5. **Auto Reload**: Browsers automatically reload when notified

## Dependencies Added
- `chokidar@^3.5.3`: File system watcher
- `ws@^8.14.2`: WebSocket server

## Live Reload Script
The injected script:
- Connects to WebSocket server at `/__live-reload__`
- Automatically reloads page when rebuild completes
- Handles connection drops by reloading after 1 second delay
- Works with HTTPS using secure WebSocket (wss)

## Testing
All tests are isolated using temporary directories and random ports to prevent conflicts.
Tests properly clean up server resources using the `close()` method.

## Backward Compatibility
- All existing build functionality preserved
- No changes to existing test suites required
- Build command operates independently of serve functionality
