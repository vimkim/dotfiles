#!/usr/bin/env bash
set -euo pipefail

mathjax_version="3.2.2"
mermaid_version="11.16.1"
config_root="${XDG_CONFIG_HOME:-${HOME}/.config}/copyparty"
data_root="${XDG_DATA_HOME:-${HOME}/.local/share}/copyparty"
docs_root="${1:-${HOME}/gh/my-cubrid-docs}"
release_dir="${data_root}/web/mathjax-${mathjax_version}_mermaid-${mermaid_version}"
web_link="${docs_root}/_copyparty_web"

if [[ ! -d "${docs_root}" ]]; then
    echo "copyparty document root does not exist: ${docs_root}" >&2
    exit 1
fi

if [[ ! -f "${config_root}/web/copyparty-render.js" ]]; then
    echo "managed renderer helper is missing: ${config_root}/web/copyparty-render.js" >&2
    exit 1
fi

stage_dir="$(mktemp -d "${TMPDIR:-/tmp}/copyparty-render.XXXXXXXX")"
cleanup() {
    rm -rf -- "${stage_dir}"
}
trap cleanup EXIT

mkdir -p "${release_dir}/vendor/mathjax" "${release_dir}/vendor/mermaid"

if [[ ! -f "${release_dir}/vendor/mathjax/es5/tex-chtml.js" ]]; then
    mathjax_archive="$(npm pack "mathjax@${mathjax_version}" --silent --pack-destination "${stage_dir}")"
    tar -xzf "${stage_dir}/${mathjax_archive}" \
        -C "${release_dir}/vendor/mathjax" \
        --strip-components=1
fi

if [[ ! -f "${release_dir}/vendor/mermaid/mermaid.min.js" ]]; then
    mermaid_archive="$(npm pack "mermaid@${mermaid_version}" --silent --pack-destination "${stage_dir}")"
    tar -xzf "${stage_dir}/${mermaid_archive}" \
        -C "${release_dir}/vendor/mermaid" \
        --strip-components=2 \
        package/dist/mermaid.min.js
    tar -xzf "${stage_dir}/${mermaid_archive}" \
        -C "${release_dir}/vendor/mermaid" \
        --strip-components=1 \
        package/LICENSE
fi

install -m 0644 \
    "${config_root}/web/copyparty-render.js" \
    "${release_dir}/copyparty-render.js"

if [[ -L "${web_link}" ]]; then
    if [[ "$(readlink -f "${web_link}")" != "$(readlink -f "${release_dir}")" ]]; then
        echo "refusing to replace existing symlink: ${web_link}" >&2
        exit 1
    fi
elif [[ -e "${web_link}" ]]; then
    echo "refusing to replace existing path: ${web_link}" >&2
    exit 1
else
    ln -s "${release_dir}" "${web_link}"
fi

echo "copyparty renderer assets installed in ${release_dir}"
