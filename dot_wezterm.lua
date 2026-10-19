local wezterm = require("wezterm")

-- This will hold the configuration.
local config = wezterm.config_builder()

-- Open remote absolute paths in the browser on this WezTerm client.
local remote_file_base = "https://dev2.baboon-rudd.ts.net:8443"

local function remote_file_url(uri)
	local path = uri:match("^remote%-file:(/.*)")
	local encoded = false
	if not path then
		path = uri:match("^file://[^/]*(/[^?#]*)")
			or uri:match("^vscode://file(/[^?#]*)")
			or uri:match("^vscode%-insiders://file(/[^?#]*)")
			or uri:match("^cursor://file(/[^?#]*)")
			or uri:match("^windsurf://file(/[^?#]*)")
		encoded = true
	end
	if not path then
		return
	end
	-- Source citations often append :line:column or #Lline to a filename.
	path = path:gsub("#L%d+.*$", ""):gsub(":%d+:%d+$", ""):gsub(":%d+$", "")
	if encoded then
		path = path:gsub("%%(%x%x)", function(hex)
			return string.char(tonumber(hex, 16))
		end)
	end
	path = path:gsub("[^A-Za-z0-9/._~-]", function(byte)
		return string.format("%%%02X", string.byte(byte))
	end)
	return remote_file_base .. path
end

config.hyperlink_rules = wezterm.default_hyperlink_rules()
table.insert(config.hyperlink_rules, {
	-- Keep URL detection first. Require a delimiter so URL paths and relative
	-- paths do not become separate absolute links. Spaces require an OSC 8 link.
	regex = [=[(?:^|[\s"'`(<\[{])(/[^\s"'`<>()\[\]{}]*[^\s"'`<>()\[\]{}.,;!?])]=],
	format = "remote-file:$1",
	highlight = 1,
})

wezterm.on("open-uri", function(window, pane, uri)
	local url = remote_file_url(uri)
	if url then
		wezterm.open_with(url)
		return false
	end
end)

-- Ctrl-click outside mouse-reporting apps; Ctrl+Shift-click also works in
-- Codex and Herdr without disabling their normal mouse controls.
config.mouse_bindings = {}
for _, binding in ipairs({
	{ mods = "CTRL", mouse_reporting = false },
	{ mods = "CTRL|SHIFT", mouse_reporting = false },
	{ mods = "CTRL|SHIFT", mouse_reporting = true },
}) do
	for _, event in ipairs({ "Down", "Up" }) do
		table.insert(config.mouse_bindings, {
			event = { [event] = { streak = 1, button = "Left" } },
			mods = binding.mods,
			mouse_reporting = binding.mouse_reporting,
			action = event == "Down" and wezterm.action.Nop or wezterm.action.OpenLinkAtMouseCursor,
		})
	end
end

-- config.color_scheme = "Catppuccin Mocha"
-- config.color_scheme = "Catppuccin Frappe"
config.color_scheme = "Catppuccin Macchiato"
--  config.color_scheme = "Catppuccin Latte"

-- config.font = wezterm.font("JetBrainsMonoNL Nerd Font Propo", { weight = "Bold" })
-- config.font = wezterm.font("NotoSansM Nerd Font Propo", { weight = "Bold" })
config.font = wezterm.font_with_fallback({
	{ family = "Maple Mono NF", weight = "Bold" },
	{ family = "Noto Sans Mono CJK KR", weight = "Bold" },
})
config.font_size = 12.0
config.line_height = 0.85

config.enable_tab_bar = false

local xdg_config_home = os.getenv("HOME")
-- config.background = {
-- 	-- first layer
-- 	{
-- 		-- Use an image as the background
-- 		source = {
-- 			-- File = xdg_config_home .. "/Pictures/arch-catppuccin-blurred.png", -- Provide the path to the image file
-- 			File = xdg_config_home .. "/.config/my-bg-imgs/arch-magenta.png", -- Provide the path to the image file
-- 		},
--
-- 		repeat_x = "NoRepeat",
-- 		horizontal_align = "Center",
-- 	},
-- 	-- second layer
-- 	{
-- 		source = {
-- 			Color = "rgba(48, 52, 70, 0.95)",
-- 		},
-- 		opacity = 0.85,
-- 		height = "100%",
-- 		width = "100%",
-- 	},
-- }

config.enable_tab_bar = true
config.hide_tab_bar_if_only_one_tab = true

-- Start maximized
-- Refer to: https://wezterm.org/config/lua/gui-events/gui-startup.html
local mux = wezterm.mux
wezterm.on("gui-startup", function(cmd)
	local _, _, window = mux.spawn_window(cmd or {})
	window:gui_window():maximize()
end)

config.window_padding = {
	left = "0%",
	right = "0%",
	top = "0%",
	bottom = "0%",
}

-- For Presentation on Screen
-- config.window_padding = {
-- 	left = "3%",
-- 	right = "3%",
-- 	top = "0%",
-- 	bottom = "3%",
-- }

return config
