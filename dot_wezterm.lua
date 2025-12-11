local wezterm = require("wezterm")

-- This will hold the configuration.
local config = wezterm.config_builder()

-- config.color_scheme = "Catppuccin Mocha"
-- config.color_scheme = "Catppuccin Frappe"
config.color_scheme = "Catppuccin Macchiato"
--  config.color_scheme = "Catppuccin Latte"

-- config.font = wezterm.font("JetBrainsMonoNL Nerd Font Propo", { weight = "Bold" })
-- config.font = wezterm.font("NotoSansM Nerd Font Propo", { weight = "Bold" })
-- config.font = wezterm.font("Maple Mono", { weight = "Bold" })
config.font = wezterm.font_with_fallback({
	{ family = "Maple Mono", weight = "Bold" },
	{ family = "NanumGothicCoding", weight = "Bold" },
	-- { family = "Noto Serif CJK KR", weight = "DemiBold" },
	{ family = "NanumBarunpen", weight = "Bold" },
})
config.font_size = 15.0
config.line_height = 1.0

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

config.window_decorations = "RESIZE"
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
