(function () {
    "use strict";

    var loader = document.currentScript;
    var nonce = loader ? (loader.nonce || loader.getAttribute("nonce") || "") : "";
    var assetRoot = new URL("/_copyparty_web/", window.location.origin);

    function loadScript(path, id) {
        return new Promise(function (resolve, reject) {
            var existing = document.getElementById(id);
            if (existing) {
                if (existing.dataset.loaded === "true") {
                    resolve();
                    return;
                }
                existing.addEventListener("load", resolve, { once: true });
                existing.addEventListener("error", reject, { once: true });
                return;
            }

            var script = document.createElement("script");
            script.id = id;
            script.src = new URL(path, assetRoot).href;
            script.async = true;
            if (nonce) {
                script.nonce = nonce;
            }
            script.addEventListener("load", function () {
                script.dataset.loaded = "true";
                resolve();
            }, { once: true });
            script.addEventListener("error", reject, { once: true });
            document.head.appendChild(script);
        });
    }

    function replaceMermaidBlocks(root) {
        var nodes = [];
        var blocks = root.querySelectorAll("pre");
        for (var i = 0; i < blocks.length; i++) {
            var block = blocks[i];
            if (!block.querySelector("code.language-mermaid")) {
                continue;
            }

            var diagram = document.createElement("div");
            diagram.className = "mermaid";
            diagram.textContent = block.textContent.trim();
            block.parentNode.replaceChild(diagram, block);
            nodes.push(diagram);
        }
        return nodes;
    }

    function showFailure(error) {
        console.error("copyparty Markdown renderer extension failed", error);
        var root = document.getElementById("mp");
        if (!root || document.getElementById("copyparty-render-error")) {
            return;
        }
        var message = document.createElement("p");
        message.id = "copyparty-render-error";
        message.style.color = "#d33";
        message.textContent = "MathJax/Mermaid rendering failed; see the browser console.";
        root.prepend(message);
    }

    window.MathJax = {
        tex: {
            inlineMath: [["$", "$"], ["\\(", "\\)"]],
            displayMath: [["$$", "$$"], ["\\[", "\\]"]],
            processEscapes: true
        },
        options: {
            skipHtmlTags: ["script", "noscript", "style", "textarea", "pre", "code"]
        },
        startup: {
            typeset: false
        }
    };

    Promise.all([
        loadScript("vendor/mathjax/es5/tex-chtml.js", "copyparty-mathjax"),
        loadScript("vendor/mermaid/mermaid.min.js", "copyparty-mermaid")
    ]).then(function () {
        var root = document.getElementById("mp");
        if (!root) {
            throw new Error("copyparty Markdown output container #mp was not found");
        }

        window.mermaid.initialize({
            startOnLoad: false,
            securityLevel: "strict",
            theme: window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
                ? "dark"
                : "default"
        });

        return window.MathJax.startup.promise
            .then(function () {
                return window.MathJax.typesetPromise([root]);
            })
            .then(function () {
                var diagrams = replaceMermaidBlocks(root);
                if (diagrams.length) {
                    return window.mermaid.run({ nodes: diagrams });
                }
            });
    }).catch(showFailure);
})();
