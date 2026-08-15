"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DevServerPlugin = void 0;
const serve_1 = require("../serve");
/**
 * Built-in plugin that starts the development server.
 *
 * `onStart` builds the site, serves it over HTTP and begins watching the
 * content/templates directories for changes. `onEnd` tears the server down.
 */
class DevServerPlugin {
    constructor(options = {}) {
        this.options = options;
        this.name = 'dev-server';
    }
    async onStart() {
        this.handle = await (0, serve_1.startServer)(this.options);
    }
    async onEnd() {
        if (this.handle) {
            await this.handle.close();
            this.handle = undefined;
        }
    }
    get address() {
        return this.handle?.address;
    }
    get port() {
        return this.handle?.port;
    }
}
exports.DevServerPlugin = DevServerPlugin;
