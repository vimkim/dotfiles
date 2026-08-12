const os = require("node:os");
const path = require("node:path");

const userHome = os.homedir();

module.exports = {
    apps: [
        {
            name: "copyparty-docs",
            script: path.join(userHome, ".config/my-scripts/bin/copyparty-pm2.sh"),
            args: ["-p", "3923"],
            cwd: path.join(userHome, "gh/my-cubrid-docs"),
            interpreter: "none",
            autorestart: true,
            merge_logs: true
        },
        {
            name: "copyparty-develop",
            script: path.join(userHome, ".config/my-scripts/bin/copyparty-pm2.sh"),
            args: ["-p", "3924"],
            cwd: path.join(userHome, "gh/cb/develop"),
            interpreter: "none",
            autorestart: true,
            merge_logs: true
        }
    ]
};
