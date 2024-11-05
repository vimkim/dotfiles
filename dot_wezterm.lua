local wezterm = require("wezterm")

-- This will hold the configuration.
local config = wezterm.config_builder()

config.color_scheme = "Catppuccin Mocha"

local mux = wezterm.mux
wezterm.on("gui-startup", function()
  local tab, pane, window = mux.spawn_window(cmd or {})
  window:gui_window():maximize()
end)

-- config.font = wezterm.font("JetBrainsMonoNL Nerd Font Propo", { weight = "Bold" })
config.font = wezterm.font("NotoSansM Nerd Font Propo", { weight = "Bold" })
config.font_size = 15.0

config.enable_tab_bar = false

-- and finally, return the configuration to wezterm
return config
