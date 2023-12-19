if status is-interactive
    # Commands to run in interactive sessions can go here
end

 starship init fish | source

eval (/home/linuxbrew/.linuxbrew/bin/brew shellenv)


set -x PATH $HOME/.local/bin $PATH

# Navigation aliases

alias ls "ls -a"
alias ll "ls -la"

function cz
    set dir (zoxide query -l | fzf)
    if test -n "$dir"
        cd $dir
    end
end

function cx
    set dir (fdfind --type d | fzf)
    if test -n "$dir"
        cd $dir
    end
end

# Find and Open aliases

alias v "nvim"

function vx
    set file (fdfind --type f | fzf)
    if test -n "$file"
        nvim $file
    end
end

function vz
    set file (/usr/bin/ls | head -n 1)
    if test -n "$file"
        nvim -- $file
    end
end

# Config aliases

alias profile 'nvim ~/.config/fish/config.fish'

# Git aliases

alias gg "git-graph"
alias gl "git log --graph --pretty=format:\"%C(auto)%h %an%d%n%w(0,4,4)%<(50,trunc)%s\" --all"
alias gloga "git log --oneline --graph --all --decorate"
alias g "git"
alias gst "git status"
alias gsw "git switch"
alias lz "lazygit"
alias lg "lazygit"
alias gcz "~/.local/bin/cz"

# Utils aliases

alias cat "batcat"
alias bat "batcat"
alias which "which -a"

function mc
    mkdir $argv
    cd $argv
end

alias less "less -R" # with colors

# WSL aliases

alias ws "webstorm64.exe"
alias ii "explorer.exe"

function wh
    set userprofile (cmd.exe /C "echo %USERPROFILE%" 2>/dev/null | tr -d '\r')
    set wslpath (wslpath $userprofile)
    cd $wslpath
end
