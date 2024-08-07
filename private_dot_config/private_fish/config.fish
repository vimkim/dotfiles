if status is-interactive
    # Commands to run in interactive sessions can go here
    set -gx EDITOR nvim
    set -gx VISUAL nvim

    starship init fish | source

    set -x PATH $HOME/.local/bin $PATH


    # install fzf with nix
    function fish_user_key_bindings
        if command -s fzf-share >/dev/null
            source (fzf-share)/key-bindings.fish
        end

        fzf_key_bindings
    end

    # Navigation aliases

    alias l "exa -a"
    alias ls "exa -a"
    alias ll "exa -la"
    alias lt "exa -aT --icons --group-directories-first"

    functions -c cd standard_cd
    function cd
        standard_cd $argv
        ls
    end

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

    function cdroot
        set directory_x (pwd)

        while test -n "$directory_x" -a ! -e "$directory_x/.git"
            set parts (string split '/' $directory_x)
            set --erase parts[(count $parts)]
            set directory_x (string join '/' $parts)
        end

        if test -n "$directory_x"
            cd "$directory_x"
        else
            echo "Could not find closest root directory with .git child" >&2
            return 1
        end

    end

    # Find and Open aliases

    alias v nvim

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

    alias gv "/mnt/c/Program\ Files/Neovide/neovide.exe --wsl"

    # Config aliases

    alias profile 'nvim ~/.local/share/chezmoi/private_dot_config/private_fish/config.fish'
    alias nvimrc 'nvim ~/.config/nvim/init.lua'

    # Git aliases

    alias gg git-graph
    alias gl "git log --graph --pretty=format:\"%C(auto)%h %an%d%n%w(0,4,4)%<(50,trunc)%s\" --all"
    alias gloga "git log --oneline --graph --all --decorate"
    alias g git
    alias gst "git status"
    alias gsw "git switch"
    alias lz lazygit
    alias lg lazygit
    alias gcz "~/.local/bin/cz"

    # Utils aliases

    alias cat batcat
    alias which "which -a"

    function tm
        tmux new-session -A
    end

    function mc
        mkdir $argv
        cd $argv
        ls
    end

    alias windows_ip "ip route"

    alias less "less -R" # with colors

    # WSL aliases

    alias ws "webstorm64.exe"
    alias ii "explorer.exe"

    function wh
        set userprofile (cmd.exe /C "echo %USERPROFILE%" 2>/dev/null | tr -d '\r')
        set wslpath (wslpath $userprofile)
        cd $wslpath
    end

    fish_vi_key_bindings

    zoxide init fish | source

    chezmoi status

    set -gx GEM_HOME $HOME/gems

    set -gx PATH "$GEM_HOME/bin:$PATH"


end
