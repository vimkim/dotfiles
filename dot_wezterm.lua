local wezterm = require("wezterm")

-- This will hold the configuration.
local config = wezterm.config_builder()

-- config.color_scheme = "Catppuccin Mocha"
config.color_scheme = "Catppuccin Frappe"
--  config.color_scheme = "Catppuccin Latte"

-- config.font = wezterm.font("JetBrainsMonoNL Nerd Font Propo", { weight = "Bold" })
config.font = wezterm.font("NotoSansM Nerd Font Propo", { weight = "Bold" })
config.font_size = 15.0

config.enable_tab_bar = false

local xdg_config_home = os.getenv("HOME")
config.background = {
	-- first layer
	{
		-- Use an image as the background
		source = {
			-- File = xdg_config_home .. "/Pictures/arch-catppuccin-blurred.png", -- Provide the path to the image file
			File = xdg_config_home .. "/arch-magenta.png", -- Provide the path to the image file
		},

		repeat_x = "NoRepeat",
		horizontal_align = "Center",
	},
	-- second layer
	{
		source = {
			Color = "rgba(48, 52, 70, 0.95)",
		},
		opacity = 0.85,
		height = "100%",
		width = "100%",
	},
}

-- and finally, return the configuration to wezterm

config.window_decorations = "NONE"
local mux = wezterm.mux
wezterm.on("gui-startup", function(cmd)
	local _, _, window = mux.spawn_window(cmd or {})
	window:gui_window():maximize()
end)

return config
