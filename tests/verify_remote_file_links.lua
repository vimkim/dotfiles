-- Run headlessly: lua tests/verify_remote_file_links.lua
local callbacks, opened = {}, {}
package.preload.wezterm = function()
	return {
		config_builder = function() return {} end,
		default_hyperlink_rules = function() return { { regex = "https?://\\S+", format = "$0" } } end,
		on = function(event, callback) callbacks[event] = callback end,
		open_with = function(url) table.insert(opened, url) end,
		font_with_fallback = function(fonts) return fonts end,
		action = { Nop = "Nop", OpenLinkAtMouseCursor = "OpenLinkAtMouseCursor" },
		mux = {},
	}
end

local config = dofile("dot_wezterm.lua")
local base = "https://dev2.baboon-rudd.ts.net:8443"
local cases = {
	{ "remote-file:/home/vimkim/arst.txt", "/home/vimkim/arst.txt" },
	{ "remote-file:/home/vimkim/code.rs:42:3", "/home/vimkim/code.rs" },
	{ "remote-file:/tmp/code.rs#L42", "/tmp/code.rs" },
	{ "remote-file:/tmp/100%.txt", "/tmp/100%25.txt" },
	{ "remote-file:/tmp/a?b#c.txt", "/tmp/a%3Fb%23c.txt" },
	{ "remote-file:/tmp/한국어.txt", "/tmp/%ED%95%9C%EA%B5%AD%EC%96%B4.txt" },
	{ "file:///home/vimkim/a%20b.txt", "/home/vimkim/a%20b.txt" },
	{ "file://dev2/home/vimkim/code.rs#L42", "/home/vimkim/code.rs" },
	{ "file:///tmp/literal%23L42%3A3", "/tmp/literal%23L42%3A3" },
	{ "vscode://file/home/vimkim/code.rs:42:3", "/home/vimkim/code.rs" },
	{ "vscode-insiders://file/tmp/code.rs:42", "/tmp/code.rs" },
	{ "cursor://file/tmp/code.rs", "/tmp/code.rs" },
	{ "windsurf://file/tmp/code.rs", "/tmp/code.rs" },
}
for _, case in ipairs(cases) do
	assert(callbacks["open-uri"](nil, nil, case[1]) == false)
	assert(opened[#opened] == base .. case[2], case[1] .. " -> " .. opened[#opened])
end

local before = #opened
for _, uri in ipairs({ "https://example.com/home/a.txt", base .. "/tmp/a.txt", "mailto:a@example.com" }) do
	assert(callbacks["open-uri"](nil, nil, uri) == nil)
end
assert(#opened == before, "ordinary URLs must use WezTerm's default handler")
assert(#config.hyperlink_rules == 2, "preserve default URL detection")
local down, up = {}, {}
for _, binding in ipairs(config.mouse_bindings) do
	local key = binding.mods .. ":" .. tostring(binding.mouse_reporting)
	if binding.event.Down then down[key] = binding.action end
	if binding.event.Up then up[key] = binding.action end
end
for _, key in ipairs({ "CTRL:false", "CTRL|SHIFT:false", "CTRL|SHIFT:true" }) do
	assert(down[key] == "Nop" and up[key] == "OpenLinkAtMouseCursor", key)
end
assert(not up["CTRL:true"], "preserve Herdr's captured Ctrl-clicks")
print("Remote file URL conversion and mouse bindings passed (13 mappings).")
