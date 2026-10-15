// Rebuild the committed browser assets; Node/npm are unnecessary at runtime.
import { build } from "esbuild";
import { createHash } from "node:crypto";
import { cp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const directory = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(directory, "../../private_dot_config/my-scripts/share/serve-html/vendor");
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
const result = await build({
  absWorkingDir: directory,
  entryPoints: ["markdown.js", "mermaid.js", "math.js"],
  outdir: output,
  bundle: true,
  splitting: true,
  format: "esm",
  platform: "browser",
  target: ["es2022"],
  minify: true,
  legalComments: "linked",
  metafile: true,
  chunkNames: "chunks/[name]-[hash]",
  logLevel: "info",
});

const moduleRoot = path.join(directory, "node_modules");
await cp(path.join(moduleRoot, "github-markdown-css/github-markdown.css"), path.join(output, "github-markdown.css"));
await cp(path.join(moduleRoot, "katex/dist/katex.min.css"), path.join(output, "katex.css"));
await cp(path.join(moduleRoot, "katex/dist/fonts"), path.join(output, "fonts"), { recursive: true });

// Include license texts for every package used in a bundle, including transitive dependencies.
const roots = new Set([path.join(moduleRoot, "github-markdown-css"), path.join(moduleRoot, "katex")]);
for (const input of Object.keys(result.metafile.inputs)) {
  let current = path.dirname(path.resolve(directory, input));
  while (current.startsWith(moduleRoot + path.sep)) {
    try {
      const metadata = JSON.parse(await readFile(path.join(current, "package.json"), "utf8"));
      if (metadata.name && metadata.version) {
        roots.add(current);
        break;
      }
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
    current = path.dirname(current);
  }
}
const packages = [];
for (const root of [...roots].sort()) {
  const metadata = JSON.parse(await readFile(path.join(root, "package.json"), "utf8"));
  const texts = [];
  for (const name of (await readdir(root)).sort()) {
    if (/^(license|licence|copying|notice)(\.|$)/i.test(name)) {
      texts.push(`${name}\n${await readFile(path.join(root, name), "utf8")}`);
    }
  }
  packages.push({ name: metadata.name, version: metadata.version, license: metadata.license, texts });
}
await writeFile(path.join(output, "THIRD_PARTY_NOTICES.txt"), packages.map((item) =>
  `${item.name}@${item.version} (${typeof item.license === "string" ? item.license : JSON.stringify(item.license)})\n${item.texts.join("\n\n")}`,
).join("\n\n----------------------------------------\n\n") + "\n");

const files = {};
for (const filename of (await readdir(output, { recursive: true, withFileTypes: true }))
  .filter((entry) => entry.isFile())
  .map((entry) => path.relative(output, path.join(entry.parentPath, entry.name)))
  .sort()) {
  files[filename] = createHash("sha256").update(await readFile(path.join(output, filename))).digest("hex");
}
await writeFile(path.join(output, "manifest.json"), JSON.stringify({
  packages: packages.map(({ texts, ...metadata }) => metadata), files,
}, null, 2) + "\n");
