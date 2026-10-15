import { Marked, gfmHeadingId, DOMPurify } from "./vendor/markdown.js";

const content = document.getElementById("content");
const rawURL = new URL(location.href);
rawURL.hash = "";
rawURL.searchParams.set("raw", "1");
document.getElementById("raw-link").href = rawURL.href;
const filename = decodeURIComponent(location.pathname.split("/").pop());
document.getElementById("filename").textContent = filename;
document.title = `${filename} · Markdown preview`;

function renderError(element, label, source, error) {
  const details = document.createElement("details");
  details.className = "render-error";
  details.open = true;
  const summary = document.createElement("summary");
  summary.textContent = `${label}: ${error.message || error}`;
  const pre = document.createElement("pre");
  const code = document.createElement("code");
  code.textContent = source;
  pre.append(code);
  details.append(summary, pre);
  element.replaceChildren(details);
}

async function renderDocument(source) {
  const slots = [];
  // A per-document marker keeps author HTML from impersonating renderer slots.
  const marker = Array.from(crypto.getRandomValues(new Uint32Array(4))).join("-");
  function slot(kind, token) {
    const index = slots.push({ kind, token }) - 1;
    const tag = kind === "mermaid" || token.displayMode ? "div" : "span";
    return `<${tag} data-preview-slot="${marker}-${index}"></${tag}>`;
  }

  const parser = new Marked({ gfm: true, breaks: false });
  parser.use(gfmHeadingId());
  parser.use({ renderer: {
    code(token) {
      if (token.lang?.split(/\s+/)[0].toLowerCase() === "mermaid") {
        return slot("mermaid", token);
      }
      return false;
    },
  } });

  let math;
  if (source.includes("$")) {
    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = new URL("./vendor/katex.css", import.meta.url);
    document.head.append(stylesheet);
    math = await import("./vendor/math.js");
    const extension = math.markedKatex();
    // Let the extension tokenize before Markdown consumes TeX backslashes.
    // Render after sanitizing the document so KaTeX's styles/MathML survive.
    for (const rule of extension.extensions) {
      rule.renderer = (token) => slot("math", token);
    }
    parser.use(extension);
  }

  content.innerHTML = DOMPurify.sanitize(parser.parse(source), {
    FORBID_TAGS: ["style"], FORBID_ATTR: ["style"],
  });

  const diagrams = slots.filter((entry) => entry.kind === "mermaid");
  let mermaid;
  let mermaidError;
  if (diagrams.length) {
    try {
      mermaid = (await import("./vendor/mermaid.js")).default;
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "default",
        suppressErrorRendering: true,
      });
    } catch (error) {
      mermaidError = error;
    }
  }

  // Render independently: one invalid block must not hide the remaining content.
  for (const [index, { kind, token }] of slots.entries()) {
    const element = content.querySelector(`[data-preview-slot="${marker}-${index}"]`);
    if (!element) continue;
    try {
      if (kind === "mermaid") {
        if (mermaidError) throw mermaidError;
        element.classList.add("diagram");
        const { svg } = await mermaid.render(`diagram-${marker}-${index}`, token.text);
        element.innerHTML = svg;
      } else {
        math.katex.render(token.text, element, {
          displayMode: token.displayMode, throwOnError: true, trust: false,
        });
      }
    } catch (error) {
      renderError(element, kind === "mermaid" ? "Mermaid error" : "Math error", token.text, error);
    }
  }
}

try {
  const response = await fetch(rawURL, { cache: "no-store" });
  if (!response.ok) throw new Error(`Could not read Markdown (HTTP ${response.status})`);
  await renderDocument(await response.text());
  // Heading IDs appear after rendering; retry the original fragment navigation.
  if (location.hash) {
    document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView();
  }
} catch (error) {
  renderError(content, "Preview error", "Use Raw to read the document source.", error);
} finally {
  content.setAttribute("aria-busy", "false");
}
