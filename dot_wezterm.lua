local wezterm = require("wezterm")

-- This will hold the configuration.
local config = wezterm.config_builder()

config.color_scheme = "Catppuccin Mocha"

-- config.font = wezterm.font("JetBrainsMonoNL Nerd Font Propo", { weight = "Bold" })
config.font = wezterm.font("NotoSansM Nerd Font Propo", { weight = "Bold" })
config.font_size = 15.0

config.enable_tab_bar = false

local xdg_config_home = os.getenv("HOME")
-- config.background = {
-- 	{
-- 		-- Use an image as the background
-- 		source = {
-- 			File = xdg_config_home .. "/Pictures/arch-catppuccin-blurred.png", -- Provide the path to the image file
-- 		},
--
-- 		hsb = {
-- 			-- hue = 0.5,
-- 			-- saturation = 0,
-- 			-- saturation = 1.5,
-- 			-- brightness = 0.8,
-- 		},
--
-- 		repeat_x = "NoRepeat",
-- 		horizontal_align = "Center",
-- 	},
-- }

-- and finally, return the configuration to wezterm

config.window_decorations = "NONE"
local mux = wezterm.mux
wezterm.on("gui-startup", function(cmd)
	local _, _, window = mux.spawn_window(cmd or {})
	window:gui_window():maximize()
end)

return config
