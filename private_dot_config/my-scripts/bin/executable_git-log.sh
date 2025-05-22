#!/bin/bash

# Set pretty format for Git log
GIT_PRETTY_FORMAT='%C(auto)%h %C(magenta)%as%C(reset) %C(blue)%an%C(reset)%C(auto)%d %s %C(black)%C(bold)%cr%Creset'

# Default Git log options
GL_OPS_DEFAULT=(--graph --oneline --color --date-order)
GL_OPS=${GL_OPS:-}

# Run Git log with options and format
GIT_PAGER="less -iRFSX" git log "${GL_OPS_DEFAULT[@]}" $GL_OPS --pretty=format:"$GIT_PRETTY_FORMAT" "$@"
