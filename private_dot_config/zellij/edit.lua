# source ~/.config/nvim/lua/config/keymaps.lua

local function map(mode, lhs, rhs, opts)
  local options = { noremap = true, silent = true }
  if opts then
    options = vim.tbl_extend("force", options, opts)
  end
  vim.api.nvim_set_keymap(mode, lhs, rhs, options)
end

-- create new file with path under cursor
vim.api.nvim_set_keymap("n", "<leader>fn", ":e <C-R><C-F><CR>", { noremap = true, silent = true })

-- colemak keybindings

map("", "n", "gj", {})
map("", "N", "J", {})
map("", "e", "gk", {})
map("", "E", "K", {})
map("", "i", "l", {})
map("x", "i", "l", {})
map("", "I", "L", {})

map("", "l", "i", {})
map("", "L", "I", {})
map("", "k", "n", {})
map("", "K", "N", {})
map("", "j", "e", {})
map("", "J", "E", {})

map("", "gn", "n", {})
map("", "ge", "e", {})

map("i", ",s", "<ESC>", {})
map("", ",s", "<ESC>:w<CR>", {})
map("", "s,", "<ESC>:w<CR>", {})
map("", ",q", "<ESC>:bd<cr>", {})
map("", "<c-q>", "<ESC>:qa<cr>", {})

map("n", ";", ":", {})

vim.opt.number = false
vim.opt.wrap = false
vim.bo.filetype = "log"
vim.opt.clipboard = "unnamedplus"
vim.cmd[[colorscheme vim]]
vim.opt.laststatus = 0
vim.opt.cmdheight = 0
vim.cmd[[set confirm]]

