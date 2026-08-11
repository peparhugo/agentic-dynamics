"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.serve = serve;
const devserver_1 = require("./plugins/devserver");
function serve(options) {
    return (0, devserver_1.createDevServer)(options);
}
//# sourceMappingURL=serve.js.map