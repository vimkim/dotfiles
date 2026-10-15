// Run with: npm --prefix tools/serve-html-assets test
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, mkdir, rm, utimes, writeFile } from "node:fs/promises";
import http from "node:http";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test, { after, before } from "node:test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(root, "tools/serve-html-assets/package.json"));
const { chromium } = require("playwright");
const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="60"><rect width="160" height="60" fill="#0969da"/><text x="15" y="35" fill="white">External SVG</text></svg>';
const filename = "한글 review #1's ?.MD";
let directory, server, images, browser, baseURL;
let serverOutput = "";

before(async () => {
  directory = await mkdtemp(path.join(os.tmpdir(), "serve-html-browser-"));
  await mkdir(path.join(directory, "nested/figures"), { recursive: true });
  images = http.createServer((request, response) => {
    response.writeHead(200, { "Content-Type": "image/svg+xml" });
    response.end(svg);
  }).listen(0, "127.0.0.1");
  await once(images, "listening");
  const remote = `http://127.0.0.1:${images.address().port}/remote.svg`;
  await writeFile(path.join(directory, "nested/figures/architecture.svg"), svg);
  await writeFile(path.join(directory, "nested", filename), [
    "# Markdown preview", "", "## Storage layout", "",
    "| Feature | Result |", "| --- | --- |", "| Markdown | Rendered |", "",
    "- [x] Task complete", "", "~~Deleted~~", "",
    "![Relative SVG](figures/architecture.svg)", "", `![Remote SVG](${remote})`, "",
    "[Next document](../next.markdown#next-heading)", "",
    "Inline math: $E = mc^2$", "", "$$", "\\int_0^1 x^2\\,dx = \\frac{1}{3}", "$$", "",
    "```mermaid", "flowchart LR", "    A[Markdown] --> B[Preview]", "```", "",
    "```mermaid", "sequenceDiagram", "    Alice->>Bob: Hello", "```", "",
    "```python", "value = '$ordinary_code$'", "```", "",
    "`$literal_math$`", "", "## Storage layout", "",
    '<script>globalThis.previewXss = true</script>',
    '<img src="figures/architecture.svg" onload="globalThis.previewXss = true">',
    "[Unsafe](javascript:alert(1))", "",
  ].join("\n"));
  await writeFile(path.join(directory, "next.markdown"), "# Next heading\n\nYou followed a Markdown link.\n");
  await writeFile(path.join(directory, "broken.md"), [
    "# Surviving content", "", "$\\notARealCommand$", "",
    "```mermaid", "this is not a diagram", "```", "",
    "```mermaid", "flowchart LR", "A --> B", "```", "", "Final paragraph.",
  ].join("\n"));
  await writeFile(path.join(directory, "plain.md"), "# Plain document\n\nNo diagrams or equations.\n");
  await writeFile(path.join(directory, "existing.html"), "<!doctype html><title>Existing HTML</title><h1>Original page</h1>");
  await writeFile(path.join(directory, "index.html"), "<!doctype html><title>Selected index</title><h1>Root index page</h1>");
  await writeFile(path.join(directory, "nested/index.htm"), "<!doctype html><title>Selected nested index</title><h1>Nested index page</h1>");
  await mkdir(path.join(directory, "ordering/subdir"), { recursive: true });
  for (const [index, name] of ["Alpha.md", "report10.md", "report2.md", "zebra.md"].entries()) {
    const file = path.join(directory, "ordering", name);
    await writeFile(file, "# A heading unrelated to the filename\n");
    await utimes(file, 1700000000 + index, 1700000000 + index);
  }
  await utimes(path.join(directory, "ordering/subdir"), 1600000000, 1600000000);

  server = spawn("python3", ["-B", path.join(root, "private_dot_config/my-scripts/bin/executable_serve-html.py"),
    "--directory", directory, "--bind", "127.0.0.1"], { stdio: ["ignore", "pipe", "pipe"] });
  server.stdout.on("data", (data) => { serverOutput += data; });
  server.stderr.on("data", (data) => { serverOutput += data; });
  const deadline = Date.now() + 5000;
  while (!serverOutput.includes("Ctrl+C")) {
    if (server.exitCode !== null || Date.now() > deadline) throw new Error(`Server startup failed: ${serverOutput}`);
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  baseURL = serverOutput.match(/http:\/\/127\.0\.0\.1:\d+\//)[0];
  browser = await chromium.launch({
    headless: true,
    ...(process.env.SERVE_HTML_CHROMIUM_EXECUTABLE ? { executablePath: process.env.SERVE_HTML_CHROMIUM_EXECUTABLE } : {}),
  });
});

after(async () => {
  await browser?.close();
  if (server && server.exitCode === null) {
    const stopped = once(server, "exit");
    server.kill("SIGINT");
    await stopped;
  }
  if (images?.listening) await new Promise((resolve) => images.close(resolve));
  if (directory) await rm(directory, { recursive: true, force: true });
});

async function ready(page) {
  await page.locator('#content[aria-busy="false"]').waitFor();
  assert.equal(await page.locator(".render-error").count(), 0, await page.locator("#content").innerText());
}

async function diagramsReady(page) {
  await page.waitForFunction(() => [...document.querySelectorAll(".diagram")]
    .every((element) => element.getAttribute("aria-busy") === "false"));
}

async function localOnly(page) {
  const external = [];
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.hostname !== "127.0.0.1") {
      external.push(url.href);
      await route.abort();
    } else {
      await route.continue();
    }
  });
  return external;
}

test("directories show listings until an index page is clicked", async () => {
  const page = await browser.newPage();
  try {
    await page.goto(baseURL);
    assert.equal(await page.getByRole("heading").innerText(), "Directory listing for /");
    await page.getByRole("link", { name: "index.html", exact: true }).click();
    assert.equal(await page.title(), "Selected index");
    assert.equal(await page.locator("h1").innerText(), "Root index page");
    await page.goto(baseURL + "nested");
    assert.equal(new URL(page.url()).pathname, "/nested/");
    assert.equal(await page.getByRole("heading").innerText(), "Directory listing for /nested/");
    await page.getByRole("link", { name: "index.htm", exact: true }).click();
    assert.equal(await page.title(), "Selected nested index");
    assert.equal(await page.locator("h1").innerText(), "Nested index page");
  } finally {
    await page.close();
  }
});

test("directory sorting and navigation work without JavaScript on a narrow screen", async () => {
  const page = await browser.newPage({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } });
  const labels = () => page.locator("tbody td:first-child a").allTextContents();
  try {
    await page.goto(baseURL + "ordering/");
    assert.deepEqual(await page.locator("th").allTextContents(), ["Title", "Created", "Modified"]);
    assert.deepEqual(await labels(), ["../", "zebra.md", "report2.md", "report10.md", "Alpha.md", "subdir/"]);
    await page.getByRole("link", { name: "Title · A–Z", exact: true }).click();
    assert.deepEqual(await labels(), ["../", "Alpha.md", "report10.md", "report2.md", "subdir/", "zebra.md"]);
    await page.getByRole("link", { name: "subdir/", exact: true }).click();
    assert.equal(new URL(page.url()).searchParams.get("sort"), "title");
    await page.getByRole("link", { name: "../", exact: true }).click();
    assert.equal(new URL(page.url()).searchParams.get("sort"), "title");
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  } finally { await page.close(); }
});

test("clicking a listed Markdown file renders GFM, Mermaid, math and SVGs", async () => {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const external = await localOnly(page);
  try {
    await page.goto(baseURL + "nested/");
    await page.getByRole("link", { name: filename, exact: true }).click();
    await ready(page);
    assert.equal(await page.locator("h1").innerText(), "Markdown preview");
    const bounds = await page.locator("#content").boundingBox();
    assert.ok(Math.abs(bounds.x - (page.viewportSize().width - bounds.width) / 2) < 1, "Markdown layout remains centered");
    assert.equal(await page.locator("table tbody td").first().innerText(), "Markdown");
    assert.equal(await page.locator('input[type="checkbox"]:checked').count(), 1);
    assert.equal(await page.locator("del").innerText(), "Deleted");
    assert.equal(await page.locator(".diagram svg").count(), 2);
    assert.equal(await page.locator(".katex").count(), 2);
    assert.equal(await page.locator("#storage-layout").count(), 1);
    assert.equal(await page.locator("#storage-layout-1").count(), 1);
    assert.match(await page.locator("code.language-python").innerText(), /\$ordinary_code\$/);
    assert.equal(await page.locator("code").filter({ hasText: "$literal_math$" }).count(), 1);
    await page.waitForFunction(() => [...document.querySelectorAll("#content img")].every((image) => image.complete && image.naturalWidth > 0));
    assert.equal(await page.locator("#content img").count(), 3);
    assert.equal(await page.evaluate(() => globalThis.previewXss), undefined);
    assert.equal(await page.locator('#content script, #content [onload], #content a[href^="javascript:"]').count(), 0);
    assert.deepEqual(external, []);
    assert.deepEqual(errors, []);
    if (process.env.SERVE_HTML_SCREENSHOT) {
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({ path: process.env.SERVE_HTML_SCREENSHOT, fullPage: true });
    }
    await page.getByRole("link", { name: "Next document", exact: true }).click();
    await ready(page);
    assert.equal(await page.locator("h1").innerText(), "Next heading");
    assert.equal(new URL(page.url()).hash, "#next-heading");
  } finally {
    await page.close();
  }
});

test("direct encoded URLs and Raw links work without a preview suffix", async () => {
  const page = await browser.newPage();
  try {
    const url = baseURL + "nested/" + encodeURIComponent(filename);
    await page.goto(url + "#storage-layout");
    await ready(page);
    assert.equal(await page.locator("#filename").innerText(), filename);
    await page.getByRole("link", { name: "Raw", exact: true }).click();
    assert.equal(new URL(page.url()).searchParams.get("raw"), "1");
    assert.match(await page.locator("body").innerText(), /^# Markdown preview/);
    assert.equal(await page.locator(".markdown-body").count(), 0);
  } finally {
    await page.close();
  }
});

test("invalid math and Mermaid blocks leave the rest of the document rendered", async () => {
  const page = await browser.newPage();
  try {
    await page.goto(baseURL + "broken.md");
    await page.locator('#content[aria-busy="false"]').waitFor();
    assert.equal(await page.locator(".render-error").count(), 2);
    assert.equal(await page.locator(".diagram svg").count(), 1);
    assert.match(await page.locator("#content").innerText(), /Final paragraph\./);
  } finally {
    await page.close();
  }
});

test("plain Markdown avoids downloading Mermaid and math bundles", async () => {
  const page = await browser.newPage();
  const urls = [];
  page.on("request", (request) => urls.push(request.url()));
  try {
    await page.goto(baseURL + "plain.md");
    await ready(page);
    assert.equal(await page.locator("h1").innerText(), "Plain document");
    await page.getByRole("button", { name: "Dark mode", exact: true }).click();
    assert.equal(urls.some((url) => /\/(mermaid|math)\.js|katex\.css/.test(url)), false);
  } finally {
    await page.close();
  }
});

test("light defaults override dark OS preference and the toggle persists across pages", async () => {
  const page = await browser.newPage({ colorScheme: "dark", viewport: { width: 390, height: 844 } });
  try {
    await page.goto(baseURL + "nested/" + encodeURIComponent(filename));
    await ready(page);
    assert.equal(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), "rgb(255, 255, 255)");
    assert.equal(await page.locator(".markdown-body").evaluate((element) => getComputedStyle(element).backgroundColor), "rgb(255, 255, 255)");
    assert.equal(await page.locator(".diagram svg").count(), 2);
    assert.equal(await page.locator(".katex").count(), 2);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const heading = await page.locator("#storage-layout").elementHandle();
    const math = await page.locator(".katex").first().elementHandle();
    const fill = () => page.locator(".diagram .node rect").first().evaluate((element) => getComputedStyle(element).fill);
    const lightFill = await fill();
    const button = page.getByRole("button", { name: "Dark mode", exact: true });
    await button.focus();
    await button.press("Space");
    await diagramsReady(page);
    assert.notEqual(await fill(), lightFill);
    assert.equal(await button.getAttribute("aria-pressed"), "true");
    assert.equal(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), "rgb(13, 17, 23)");
    assert.equal(await page.locator(".markdown-body").evaluate((element) => getComputedStyle(element).backgroundColor), "rgb(13, 17, 23)");
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.equal(await heading.evaluate((element) => element.isConnected), true);
    assert.equal(await math.evaluate((element) => element.isConnected), true);
    assert.equal(await button.evaluate((element) => document.activeElement === element), true);
    assert.equal(await button.evaluate((element) => getComputedStyle(element).outlineWidth), "2px");
    await page.getByRole("link", { name: "Next document", exact: true }).click();
    await ready(page);
    assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
    await page.reload();
    await ready(page);
    assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
    await button.click();
    await page.reload();
    await ready(page);
    assert.equal(await page.locator("html").getAttribute("data-theme"), "light");
  } finally {
    await page.close();
  }
});

test("initial theme and toggle do not wait for the Markdown fetch", { timeout: 30000 }, async () => {
  for (const saved of [null, "dark"]) {
    const page = await browser.newPage({ colorScheme: "dark" });
    let release, requested;
    const gate = new Promise((resolve) => { release = resolve; });
    const started = new Promise((resolve) => { requested = resolve; });
    try {
      if (saved) await page.addInitScript((value) => localStorage.setItem("serve-html.theme.v1", value), saved);
      await page.route("**/*", async (route) => {
        if (new URL(route.request().url()).searchParams.get("raw") === "1") {
          requested();
          await gate;
        }
        await route.continue();
      });
      await page.goto(baseURL + "plain.md", { waitUntil: "commit" });
      await started;
      const button = page.getByRole("button", { name: "Dark mode", exact: true });
      await button.waitFor();
      assert.equal(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), saved ? "rgb(13, 17, 23)" : "rgb(255, 255, 255)");
      await button.click();
      assert.equal(await button.getAttribute("aria-pressed"), saved ? "false" : "true");
      release();
      await ready(page);
    } finally { release(); await page.close(); }
  }
});

test("invalid and denied storage still allow a usable theme toggle", async () => {
  for (const mode of ["invalid", "read-denied", "write-denied"]) {
    const page = await browser.newPage({ colorScheme: "dark" });
    try {
      await page.addInitScript((mode) => {
        if (mode === "invalid") localStorage.setItem("serve-html.theme.v1", "system");
        if (mode === "read-denied") Object.defineProperty(window, "localStorage", { get() { throw new DOMException("Denied", "SecurityError"); } });
        if (mode === "write-denied") Storage.prototype.setItem = () => { throw new DOMException("Full", "QuotaExceededError"); };
      }, mode);
      await page.goto(baseURL + "plain.md");
      await ready(page);
      assert.equal(await page.locator("html").getAttribute("data-theme"), "light");
      const button = page.getByRole("button", { name: "Dark mode", exact: true });
      await button.click();
      assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
      await button.click();
      assert.equal(await page.locator("html").getAttribute("data-theme"), "light");
    } finally { await page.close(); }
  }
});

test("rapid toggles during delayed Mermaid loading finish in the latest theme", { timeout: 30000 }, async () => {
  const page = await browser.newPage();
  let release, requested;
  const gate = new Promise((resolve) => { release = resolve; });
  const started = new Promise((resolve) => { requested = resolve; });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await page.route("**/vendor/mermaid.js", async (route) => {
      requested();
      await gate;
      await route.continue();
    });
    await page.goto(baseURL + "nested/" + encodeURIComponent(filename), { waitUntil: "domcontentloaded" });
    await started;
    await page.getByRole("button", { name: "Dark mode", exact: true }).evaluate((button) => {
      button.click(); button.click(); button.click();
    });
    release();
    await ready(page);
    assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
    const fill = () => page.locator(".diagram .node rect").first().evaluate((element) => getComputedStyle(element).fill);
    const darkFill = await fill();
    const button = page.getByRole("button", { name: "Dark mode", exact: true });
    await button.click();
    await diagramsReady(page);
    assert.notEqual(await fill(), darkFill);
    await button.evaluate((button) => { for (let i = 0; i < 5; i += 1) button.click(); });
    await diagramsReady(page);
    assert.equal(await fill(), darkFill);
    assert.deepEqual(errors, []);
  } finally { release(); await page.close(); }
});

test("diagram errors do not prevent theme changes", async () => {
  const page = await browser.newPage();
  try {
    await page.goto(baseURL + "broken.md");
    await page.locator('#content[aria-busy="false"]').waitFor();
    await page.getByRole("button", { name: "Dark mode", exact: true }).click();
    await diagramsReady(page);
    assert.equal(await page.locator(".render-error").count(), 2);
    assert.equal(await page.locator(".diagram svg").count(), 1);
    assert.match(await page.locator("#content").innerText(), /Final paragraph\./);
  } finally { await page.close(); }
});

test("a failed theme script leaves a light preview and hides the inactive toggle", async () => {
  const page = await browser.newPage({ colorScheme: "dark" });
  try {
    await page.route("**/__serve_html__/theme.js", (route) => route.abort());
    await page.goto(baseURL + "plain.md");
    await ready(page);
    assert.equal(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), "rgb(255, 255, 255)");
    assert.equal(await page.locator("#theme-toggle").isVisible(), false);
  } finally { await page.close(); }
});

test("existing HTML is still served unchanged", async () => {
  const page = await browser.newPage();
  try {
    await page.goto(baseURL + "existing.html");
    assert.equal(await page.title(), "Existing HTML");
    assert.equal(await page.locator("h1").innerText(), "Original page");
  } finally {
    await page.close();
  }
});
