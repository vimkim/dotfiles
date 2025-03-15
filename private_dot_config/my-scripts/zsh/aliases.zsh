# vim: filetype=zsh
# alias begin

export EDITOR='nvim'
# export CHEZ_EDITOR='chezmoi edit --watch'
# export CHEZ_EDITOR='nvim' # thanks to chezmoi plugin

chez-open () {
    nvim $(chezmoi source-path $@)
}
export CHEZ_EDITOR='chez-open'

alias nvimrc="$EDITOR ~/.config/nvim/init.lua"
alias nvimh="cd ~/.config/nvim"
alias nvimd="cd ~/.config/nvim"
alias tmuxconf="$CHEZ_EDITOR ~/.tmux.conf.local"
alias zellconf="$CHEZ_EDITOR ~/.config/zellij/config.kdl"

# Config profiles
alias bashrc="$CHEZ_EDITOR ~/.bashrc"
alias zshrc="$CHEZ_EDITOR ~/.zshrc"
alias profile="zshrc"
alias vimprofile="$EDITOR ~/.vimrc"
alias nvimrc="$EDITOR ~/.config/nvim/init.lua"
alias gdbinit="$CHEZ_EDITOR ~/.config/gdb/gdbinit"

# System aliases
# alias rm='rm -i'
alias rm='trash'

alias ls='ls -aF'
alias l='ls -AF'
alias la='ls -lAF'
alias ll='ls -lAF'

# Function to check if a command exists
function command_exists {
    command -v "$1" >/dev/null 2>&1
}

# Conditionally set alias for `dust`
if command_exists dust; then
    alias du='dust'
fi

# Conditionally set alias for `bat`
if command_exists bat; then
    alias cat='bat'
    alias bh='bat -l help'
    export MANPAGER="sh -c 'sed -u -e \"s/\\x1B\[[0-9;]*m//g; s/.\\x08//g\" | bat -p -lman'" # as recommended in bat repo readme

    function help-bat() {
        $@ --help | bat -l help -p
    }
    alias h='help-bat'

fi

# Conditionally set alias for `broot`
if command_exists broot; then
    alias tree='broot'
fi

if command_exists delta; then
    # alias diff='delta'
    source <(delta --generate-completion zsh)
elif command_exists difft; then
    alias diff='difft --color=always'
fi

if [ -x "$(command -v eza)" ]; then

    export EZA_COLORS="da=35;$EZA_COLORS"
    export EZA_COMMON_OPTIONS=(--group-directories-last -aF -r --time-style=relative)
    export EZA_LONG_OPTIONS=($EZA_COMMON_OPTIONS --long --git --color=always)
    export EZA_SORT_MODIFIED=(--sort=modified -r)
    alias lss="eza $EZA_COMMON_OPTIONS --icons $EZA_SORT_MODIFIED"
    alias la='lss'
    alias llsz="eza --no-user --no-permissions $EZA_LONG_OPTIONS --icons --total-size --sort=size -r"
    alias lll="eza $EZA_LONG_OPTIONS $EZA_SORT_MODIFIED --header --inode | less -RFiX" # no icons since modern less -r usage not recommended

    function my-list-long() {
        git_root=$(git rev-parse --show-toplevel 2>/dev/null)
        if [[ -n $git_root ]]; then
            my-git-status
        fi
        eza --no-user --no-permissions $EZA_LONG_OPTIONS --icons $EZA_SORT_MODIFIED --grid $@
    }
    alias ll='my-list-long'
    alias ls='my-list-long'
    alias l='my-list-long'
elif [ -x "$(command -v lsd)" ]; then
    alias ls='lsd -aF'
    alias l='lsd -aF'
    alias la='lsd -laF'
    alias ll='lsd -laF'
    alias llg='lsd -laF --git'
fi


alias pfzf='ps -ef | fzf | awk "{print \$2}"'
alias pscp='ps -ef | fzf | awk "{print \$2}" | xclip -selection clipboard'
if [ -x "$(command -v procs)" ]; then
    alias pps='procs'
    alias ppstt='procs --tree --thread'
    pscopy() {
        local selection=$(procs --no-header --color=always | fzf --ansi --height 40%)
        local pid=$(echo "$selection" | awk '{print $1}')
        procs $pid
        echo "$pid" | xclip -selection clipboard # Copy only the PID to the clipboard
    }

    alias pscp='pscopy'
    source <(procs --gen-completion-out zsh)
fi

alias penv='env | fzf --exact -i'

alias lzd='lazydocker'

alias lzp='sudo env DOCKER_HOST=unix:///run/podman/podman.sock PATH=$PATH lazydocker'
alias lazypodman='lzp'

alias lzpu='DOCKER_HOST=unix:///run/user/1000/podman/podman.sock lazydocker'
alias lazypodman_user='lzpu'

alias sl='ls'

# https://github.com/jesseduffield/lazygit?tab=readme-ov-file#changing-directory-on-exit
lg()
{
    export LAZYGIT_NEW_DIR_FILE=~/.lazygit/newdir

    lazygit "$@"

    if [ -f $LAZYGIT_NEW_DIR_FILE ]; then
        cd "$(cat $LAZYGIT_NEW_DIR_FILE)"
        rm -f $LAZYGIT_NEW_DIR_FILE > /dev/null
    fi
}
alias lz='lg'

alias wa="which -a"
which-alias() {
    alias | grep "^$1"
}

alias ppath='echo "$PATH" | tr ":" "\n" | nl'

## Safety Features
alias cp='cp -i' # confirm before overwriting something
alias mv='mv -i' # confirm before overwriting something

## utility aliases
mc() {
    mkdir $@
    cd $@
}

## editor aliases
alias nv='nvim'
alias v='nvim'
alias vim='nvim'
alias vv='FILE=$(fd . -H -I --type f --type l --max-depth 1 | fzf --height 40% --reverse) && [[ -n $FILE ]] && $EDITOR "$FILE"'
alias vc='vv'
alias vx='FILE=$(fd . -H -I --type f --type l | fzf --height 40% --reverse) && [[ -n $FILE ]] && $EDITOR "$FILE"'

alias nf="newfile.sh"

alias fdall='fd -H -I'
alias fda='fd -H -I'
alias rgall='rg --no-ignore -.'
alias rga='rg --no-ignore -.'
alias tg='tgrep'
alias gg='git grep -n -p -C 5'

function fdrg() {
    fd "$1" -H -I --type f -X rg "$2"
}

function relative_gitdir() {
    local git_root rel_path
    git_root=$(git rev-parse --show-toplevel 2>/dev/null) || return 1
    rel_path=$(realpath --relative-to="$PWD" "$git_root") || return 1
    echo "$rel_path"
}

function vxg() {

    local workspace_dir
    workspace_dir=$(relative_gitdir 2>/dev/null || echo ".")
    echo $workspace_dir

    local file_to_open
    file_to_open=$(fd --type f . "$workspace_dir" --base-directory "." | fzf --height 40% --reverse)

    if ! [ -f "$file_to_open" ]; then
        echo "No file selected"
        return
    fi

    $EDITOR "$file_to_open"
}
alias vxg='vxg'

## Navigation aliases
function cl() {
    builtin cd "$@" && my-list-long
}


# Function to compare two directories using diff and delta
diff_dir() {
    if [[ -d "$1" && -d "$2" ]]; then
        /bin/diff -ur "$1" "$2" | delta
    else
        echo "Please provide two valid directories."
    fi
}
alias ddr='diff_dir'

# Function to compare two directories using diff and diffstat
diff_dir_stat() {
    if [[ -d "$1" && -d "$2" ]]; then
        /bin/diff -ur "$1" "$2" | diffstat -C
    else
        echo "Please provide two valid directories."
    fi
}
alias ddrstat='diff_dir_stat'


function cdfile() {
    if [[ -z "$1" ]]; then
        echo "Usage: cdtofile <filepath>"
        return 1
    fi

    local dir_path=$(dirname "$(realpath "$1")")

    if [[ -d "$dir_path" ]]; then
        cd "$dir_path" || return
        echo "Changed directory to: $dir_path"
    else
        echo "Error: Directory does not exist."
        return 1
    fi
}

alias cd='cl'
alias cz='DIR=$(zoxide query -l | fzf --height 40% --reverse) && [[ -n $DIR ]] && cd "$DIR"'
alias cr='DIR=$(dirs -v | sed "1d" | head -n 20 | awk '\''{print $2}'\'' | fzf --height 40% --reverse) && [[ -n $DIR ]] && eval cd "$DIR"'
alias ch='DIR=$(cat $HOME/.zdirs | head -n 20 | fzf --height 40% --reverse) && [[ -n $DIR ]] && eval cd "$DIR"'
alias co='popd >/dev/null'

# in order to include ".." to the selection list supplied to fzf, use $dirs
cv() {
    # If an argument is provided, act like 'cd' and go to that directory
    if [[ -n $1 ]]; then
        cl "$1"
        return
    fi

    # Combine the parent directory and subdirectories into an array
    local dirs=("../" $(fd --max-depth 1 -H -I --type d --type l -L --strip-cwd-prefix))
    # Pass the array to fzf for selection
    local dir=$(printf "%s\n" "${dirs[@]}" | fzf --height 40% --reverse)
    # If a directory was selected, change to that directory
    [[ -n $dir ]] && cd "$dir"
}
alias c='cv'

alias H='cd ..'

# alias cx='DIR=$(fd . -H -I --type d | fzf --height 40% --reverse) && [[ -n $DIR ]] && cd "$DIR"'
# alias cxh='DIR=$(fd . -H -I --type d $HOME | fzf) && [[ -n $DIR ]] && cd "$DIR"'
# alias cxg='DIR=$(fd . -H -I --type d $(relative_gitdir) | fzf) && [[ -n $DIR ]] && cd "$DIR"'

# Unified function for navigation
function cd_fzf() {
    local search_path="${1:-.}"

    # Build the fd command with optional type filtering
    local OBJECT=$(fd . -H -I $FD_OPS "$search_path" | fzf --height 40% --reverse)

    # Check if a selection was made and navigate accordingly
    if [[ -n $OBJECT ]]; then
        if [[ -d $OBJECT ]]; then
            cd "$OBJECT"
        elif [[ -f $OBJECT ]]; then
            cd "$(dirname "$OBJECT")"
        fi
    fi
}

# Aliases for specific navigation
alias cx='FD_OPS=(--type d --type l) cd_fzf .'          # Navigate to directories
alias cxh='cd_fzf "$HOME" d'   # Navigate to directories under $HOME
alias cxg='cd_fzf "$(relative_gitdir)" d'  # Navigate to directories under Git root

alias cf='FD_OPS=(--type f --type l --follow) cd_fzf .'          # Navigate to file-containing directories
alias cfh='cd_fzf "$HOME" f'   # Navigate to file-containing directories under $HOME
alias cfg='cd_fzf "$(relative_gitdir)" f'  # Navigate to file-containing directories under Git root

alias ca='FD_OPS=(-tf -td -tl) cd_fzf .'              # Navigate to either files or directories
alias cb='cd "$(cat ~/.directory_bookmarks | fzf --prompt="Select a directory: ") || echo "No directory selected." >&2"'


alias ff='vxg'

alias gcd='cd $(relative_gitdir 2>/dev/null || echo ".")'
alias cdg='gcd'
alias pcd='gcd'
alias cdw='gcd'

alias cg='cargo'

alias back='cd $OLDPWD'                                    # Return to the previous directory

## Networking and System Information
alias ports='netstat -tulanp'
alias ipinfo='curl ipinfo.io' # Quick IP address and network info
alias myip='curl http://ipecho.net/plain' # External IP address

export MYFZF_OPS=(--height 40% --reverse)
# Git Aliases
# alias ga='git add'
alias gc='git commit'
alias gcm='git commit -m'
alias gcv='git commit --verbose'
alias git_checkout_child='git checkout $(git log --all --ancestry-path ^HEAD --format=format:%H | tail -n 1)'
alias gup='git_checkout_child'
alias gdown='git checkout HEAD~1'
alias grs='git reset'
alias git-assume-unchanged-list='git ls-files -v | grep "^h"'
alias git-assume-unchanged-add='git update-index --assume-unchanged'
alias git-assume-unchanged-add-interactive='git status --porcelain=v1 | awk "{print \$2}" | fzf $MYFZF_OPS | xargs git update-index --assume-unchanged && echo "added."'

export MY_SCRIPTS="$HOME/.config/my-scripts"
alias rfv='$MY_SCRIPTS/rfv.sh'
alias frf='$MY_SCRIPTS/frf.sh'

export GBFLIMIT=99
git_blame_file() {
    file=$1
    max_length=10
    if [ -d "$file" ]; then
        file="$file/"
    fi
    commit_info=$(git log --follow --color=always -1 --format="%C(green)%Creset %C(red)%h%Creset %C(yellow)%as%Creset %C(cyan)%an%Creset %C(white)%s%Creset" -- "$file")
    printf "%-${max_length}s | %s\n" "$file" "$commit_info"
}
alias gbf='git_blame_file'

git_blame_file_long() {
    file=$1
    max_length=10
    if [ -d "$file" ]; then
        file="$file/"
    fi
    commit_info=$(git log --follow --stat --oneline -n $GBFLIMIT --color=always --format="%C(green)%Creset %C(red)%h%Creset %C(yellow)%as%Creset %C(cyan)%an%Creset %C(white)%s%Creset" -- "$file")
    # printf "%s\n" "$commit_info"

    echo "$commit_info" | while IFS= read -r line; do
        stripped_line=$(echo "$line" | sed 's/\x1b\[[0-9;]*m//g')

        # Skip blank lines and lines containing 'file changed'
        if [[ -z "$stripped_line" || "$stripped_line" == *"file changed"* ]]; then
            continue
        fi

        if [[ "$stripped_line" == *"|"* ]]; then
            echo "${line#*|}"  # Print only the part after the pipe, keeping the colors
        else
            printf "%s " "$line"
        fi
    done
}

gbfl() {
    git_blame_file_long $@ | less -iRFSX
}

git_blame_directory() {
    # Find the maximum filename length for alignment
    max_length=0
    for file in "$1"/*; do
        if [ -d "$file" ]; then
            file="$file/"
        fi
        if [ ${#file} -gt $max_length ]; then
            max_length=${#file}
        fi
    done

    # Iterate through each file and display the git log in the aligned format
    for file in "$1"/*; do
        if [ -d "$file" ]; then
            file="$file/"
        fi
        commit_info=$(git log --follow --color=always -1 --format="%C(green)%Creset %C(red)%h%Creset %C(yellow)%as%Creset %C(cyan)%an%Creset %C(white)%s%Creset" -- "$file")
        printf "%-${max_length}s | %s\n" "$file" "$commit_info"
    done
}
alias gbd='git_blame_dir.py'

export GBDLIMIT=99
git_blame_directory_long() {
    # Iterate through each file and display the git log in the aligned format
    for file in "$1"/*; do
        if [ -d "$file" ]; then
            file="$file/"
        fi
        echo ""
        echo "$file"
        commit_info=$(git log --follow --stat --oneline -n $GBDLIMIT --color=always --format="%C(green)%Creset %C(red)%h%Creset %C(yellow)%as%Creset %C(cyan)%an%Creset %C(white)%s%Creset" -- "$file")
        # printf "%s\n" "$commit_info"

        echo "$commit_info" | while IFS= read -r line; do
            stripped_line=$(echo "$line" | sed 's/\x1b\[[0-9;]*m//g')

            # Skip blank lines and lines containing 'file changed'
            if [[ -z "$stripped_line" || "$stripped_line" == *"file changed"* ]]; then
                continue
            fi

            if [[ "$stripped_line" == *"|"* ]]; then
                echo "${line#*|}"  # Print only the part after the pipe, keeping the colors
            else
                printf "%s " "$line"
            fi
        done
    done

}
alias gbdl='git_blame_directory_long . | less -iRFSX'
alias lb='gbdl'

# Function to estimate Git repository size and prompt before cloning
function github-clone {
    if [ -z "$1" ]; then
        echo "Usage: github-clone <repository_url>"
        return 1
    fi

    INPUT="$1"

    # Check if the input is a full URL or just <username>/<reponame>
    if [[ "$INPUT" == https://github.com/* ]]; then
        # Extract <username>/<reponame> from the full URL
        REPO_URL=$(echo "$INPUT" | sed -E 's|https://github.com/([^/]+/[^/]+).*|\1|')
    else
        # Assume input is already in <username>/<reponame> format
        REPO_URL="$INPUT"
    fi

    # Get the repository's size in KB
    REPO_SIZE=$(curl -s "https://api.github.com/repos/$REPO_URL" | jq '.size')

    # Check if REPO_SIZE is null or empty
    if [[ -z "$REPO_SIZE" || "$REPO_SIZE" == "null" ]]; then
        echo "Error: Invalid repository name. Please input a valid GitHub repository in the form of <username>/<reponame> or a full URL."
        return 1
    fi

    # Convert the size to MB
    HUMAN_SIZE=$(echo "scale=2; $REPO_SIZE / 1024" | bc)

    echo "Repository: $REPO_URL"
    echo "Repository size: $HUMAN_SIZE MB"

    # Prompt the user for confirmation to clone
    echo "Do you want to clone the repository? (y/n): "
    read confirm

    if [ "$confirm" = "y" ]; then
        git clone https://github.com/$REPO_URL.git
    else
        echo "Clone aborted."
    fi
}


alias ghclone="github-clone"
alias ghc='github-clone'
alias ghcf='gh-clone-fuzzy.sh'
alias ghcu='$MY_SCRIPTS/bin/git-clone-user.sh'

function gitclonehash() {
    if [ $# -ne 2 ]; then
        echo "Usage: gitclonehash <repository-url> <commit-hash>"
        return 1
    fi

    local repo_url=$1
    local commit_hash=$2
    local repo_name=$(basename "$repo_url" .git)

    # Clone the repository with minimal depth
    git clone --depth 1 "$repo_url" || return 1

    # Change into the repository directory
    cd "$repo_name" || return 1

    # Fetch the specific commit
    git fetch --depth 1 origin "$commit_hash" || return 1

    # Checkout the specific commit
    git switch "$commit_hash"
}
alias gclh='gitclonehash'

## git diff
## alias gd='git diff'
alias gds='git diff --staged'
alias gdc='git diff --cached'

## git log
export GIT_PRETTY_FORMAT='%C(auto)%h %C(magenta)%as%C(reset) %C(blue)%an%C(reset)%C(auto)%d %s %C(black)%C(bold)%cr%Creset'
export FORGIT_LOG_FORMAT=$GIT_PRETTY_FORMAT

export GL_OPS_DEFAULT=(--graph --oneline --color --date-order)
export GL_OPS=''
git-log() {
    GIT_PAGER="less -iRFSX" git log $GL_OPS_DEFAULT $GL_OPS --pretty=format:"$GIT_PRETTY_FORMAT" $@
}
alias gl='git-log'
alias gla='GL_OPS=(--all) git-log'
alias gloga='GL_OPS=(--all) git-log'
alias gla-topo='GL_OPS=(--all --topo-order) git-log'
alias gla-date='GL_OPS=(--all --date-order) git-log'
alias gla-author-date='GL_OPS=(--all --author-date-order) git-log'
alias glh='git-log HEAD' # useful when followed by a branch like develop
alias gld='git-log develop HEAD'
alias glstat='GL_OPS=(--stat) GIT_PRETTY_FORMAT="$GIT_PRETTY_FORMAT%n" git-log'
alias glogastat='GL_OPS=(--all --stat) GIT_PRETTY_FORMAT="$GIT_PRETTY_FORMAT%n" git-log'
alias git-log-upstream-head='git-log $(git rev-parse upstream/$(git rev-parse --abbrev-ref HEAD)) HEAD'
alias git-log-origin-head='git-log $(git rev-parse origin/$(git rev-parse --abbrev-ref HEAD)) HEAD'
alias git-log-cub-head='git-log $(git rev-parse cub/$(git rev-parse --abbrev-ref HEAD)) HEAD'
alias gluh='git-log-upstream-head'
alias gloh='git-log-origin-head'
alias glch='git-log-cub-head'

alias git-log-cubvec='git branch --all --format="%(refname:short)" | rg cubvec | xargs -d "\n" git-log.sh develop'
alias glc='git-log-cubvec'
alias git-log-fzf='git branch --all --format="%(refname:short)" | fzf $MYFZF_OPS --multi --prompt="Select branches: " | xargs -d "\n" git-log.sh'
alias glf='git-log-fzf'
alias git-log-fzf-all='git branch --all --format="%(refname:short)" | fzf $MYFZF_OPS --multi --bind "enter:select-all+accept" | xargs -d "\n" git-log.sh'
alias glfa='git-log-fzf-all'


## git pull
alias gpl='git pull'
alias gpom='git pull origin main'

## git push
alias gfp='git fetch --prune --all'
alias gfpa='git fetch --prune --all'
alias gp='git push'
alias gps='git push'
alias gpsoh='git push origin HEAD'
alias gpoh='git push origin HEAD'

## git status
function my-git-status() {
    "$MY_SCRIPTS/gst.sh"
}
alias gst="my-git-status"
alias gs='gst'

## git switch
alias gb='git branch'
alias gsw='git switch'
# alias gco='git checkout'

function git_status_tracked() {
    if [ -z "$1" ]; then
        echo "Usage: check_git_file_status <directory_path>"
        return 1
    fi

    directory_path="$1"

    # Check if we're in a Git repository
    if ! git rev-parse --is-inside-work-tree &> /dev/null; then
        echo "Not inside a Git repository."
        return 1
    fi

    # Traverse the directory (non-recursive) and check each file
    for file in "$directory_path"/*; do
        # Only check regular files
        if [ -f "$file" ]; then
            # Remove the directory path from the file path for displaying
            relative_path="${file#$directory_path/}"

            # Check if the file is tracked by Git
            if git ls-files --error-unmatch "$file" > /dev/null 2>&1; then
                echo -e "\033[32m$relative_path [✔ Tracked]\033[0m"
            elif git check-ignore -q "$file"; then
                echo -e "\033[31m$relative_path [✖ Ignored]\033[0m"
            else
                echo -e "\033[33m$relative_path [? Untracked]\033[0m"
            fi
        fi
    done
}
alias gls='git_status_tracked'


git-ls-ignored() {
    git ls-files $@ --others --ignored --exclude-standard
}
alias gli='git-ls-ignored'


## git etc
alias gcz="~/.local/bin/cz"
alias gfz="git fuzzy"

# Deveplopment and Programming aliases

## python
alias py='python'

build_project() {
    if [ -f Cargo.toml ]; then
        echo "Detected Rust project."
        cargo run
    elif [ -f main.rs ]; then
        echo "Detected main.rs."
        rustc main.rs && ./main
    elif [ -f package.json ]; then
        echo "Detected Node.js project."
        npm start
    elif [ -f setup.py ]; then
        echo "Detected Python project."
        python setup.py
    elif [ -f main.py ]; then
        echo "Detected Python project."
        python main.py
    elif [ -f src/main.py ]; then
        echo "Detected Python project."
        python src/main.py
    elif [ -f Makefile ]; then
        echo "Detected project with Makefile."
        make
    elif [ -f go.mod ]; then
        echo "Detected Go module."
        go run .
    elif [ -f main.go ]; then
        echo "Detected Go project."
        go run main.go
    elif [ -f CMakeUserPresets.json ]; then
        echo "Detected CMake User Presets."
        # cmake --preset $ENV_MODE
        cmake --build --preset $ENV_MODE --target install
    elif [ -f CMakeLists.txt ]; then
        echo "Detected CMake project."
        # cmake -S . -B build_with_x
        cmake --build build_with_x --target install
    elif [ -f build.gradle ]; then
        echo "Detected Gradle project."
        ./gradlew run
    elif [ -f pom.xml ]; then
        echo "Detected Maven project."
        mvn compile exec:java
    elif [ -f requirements.txt ]; then
        echo "Detected Python project with requirements.txt."
        python -m pip install -r requirements.txt
        python main.py
    elif [ -f Gemfile ]; then
        echo "Detected Ruby project."
        bundle exec ruby main.rb
    elif [ -f manage.py ]; then
        echo "Detected Django project."
        python manage.py runserver
    else
        echo "No recognized project files found. Please add a specific case to the script."
    fi
}
alias x='build_project'

run_project() {
    if [ -f "cubrid/CMakeLists.txt" ]; then
        echo "Detected CUBRID project."
        csql_run
    fi
}

alias cdd='csql -u dba demodb'
alias cdds='csql -u dba demodb -S'
alias cdt='csql -u dba testdb'
alias cdts='csql -u dba testdb -S'

alias ct='cargo test'
alias ca='cargo'
alias cts='$MY_SCRIPTS/bin/cargo-test-select.sh'

test_project() {
    if [ -f Cargo.toml ]; then
        echo "Detected Rust project."
        cargo test
    else
        echo "No recognized project files found. Please add a specific case to the script."
    fi
}
alias xt='test_project'

# direnv
alias mode-debug='export ENV_MODE=debug && direnv allow'
alias mode-profile='export ENV_MODE=profile && direnv allow'
alias mode-release='export ENV_MODE=release && direnv allow'

configure_project() {
    if [ -f CMakePresets.json ]; then
        cmake --preset debug
    fi
}
alias confp='configure_project'

alias bb='build_project'
alias bp='build_project'

alias cmbd='cmake --build --preset debug'
alias cmd='cmake --preset debug'
alias cmbdi='cmake --build --preset debug --target install'

## docker
alias doc='docker' # Never use do. It is part of zsh shell grammar.
alias dc='docker compose'
alias dco='docker compose'
alias dcu='docker compose up'
alias dcub='docker compose up --build'
alias dcd='docker compose down'
alias dcr='docker compose run'
alias dcb='docker compose build'
alias dcl='docker compose logs'

# nix aliases
alias nx='nix-shell'

nix-profile-install() {
    nix profile install "nixpkgs#$@"
}
alias nixi='nix-profile-install'

## wsl aliases
if [ -x "$(command -v wslpath)" ]; then
    alias wh="cd $(wslpath $(cmd.exe /C "echo %USERPROFILE%" 2>/dev/null | tr -d '\r'))"
    alias ws="webstorm64.exe"
    alias ii="explorer.exe"
    alias open="explorer.exe"
fi

# init setup
alias com='command' # com kubernetes works as the real kubernetes, not alias

## chezmoi
alias chz='chezmoi'
alias chez='chezmoi'
alias che='chezmoi edit --watch'
alias cheze='chezmoi edit --watch'
alias chzd='cd ~/.local/share/chezmoi'
alias chzh='cd ~/.local/share/chezmoi'
alias chezd='cd ~/.local/share/chezmoi'
alias chzed='chezd' # for typo
alias chezh='cd ~/.local/share/chezmoi'
alias chezcd='cd ~/.local/share/chezmoi'

## conf
alias confd='cd ~/.config && echo "prefer using chezmoi edit"'
alias conf='confd'

source $HOME/my-cubrid/aliases.sh

alias rrkernel='sudo sysctl kernel.perf_event_paranoid=1'
alias rrkerneloff='sudo sysctl kernel.perf_event_paranoid=0'
alias rrzen='sudo $HOME/temp/rr/scripts/zen_workaround.py'

clip() {
    if grep -qi microsoft /proc/version; then
        clip.exe "$@"
    else
        xclip -selection clipboard "$@"
    fi
}


# yazi
function yy() {
    local tmp="$(mktemp -t "yazi-cwd.XXXXXX")"
    yazi "$@" --cwd-file="$tmp"
    if cwd="$(cat -- "$tmp")" && [ -n "$cwd" ] && [ "$cwd" != "$PWD" ]; then
        cd -- "$cwd"
    fi
    /bin/rm -f -- "$tmp"
}

alias y='yy'
function yazi-plugin-install() {
    ya pack -a Rolv-Apneseth/starship
    ya pack -a yazi-rs/plugins:git
    ya pack -a dawsers/dual-pane
}


gh_pr_diff() {

    if [ -z "$@" ]; then
        echo "Usage: pr_diff_fetch <repo> <pr_number>"
        return 1
    fi

    # Input GitHub PR URL
    url="$@"

    # Extract the repo (e.g., "CUBRID/cubrid")
    repo=$(echo "$url" | sed -E 's|https://github.com/([^/]+/[^/]+)/pull/.*|\1|')

    # Extract the PR number (e.g., "5511")
    pr_number=$(echo "$url" | sed -E 's|.*/pull/([0-9]+).*|\1|')

    # Print the results
    echo "Repository: $repo"
    echo "PR Number: $pr_number"

    curl -H "Accept: application/vnd.github.diff" \
        "https://api.github.com/repos/${repo}/pulls/${pr_number}"
}
alias prdiff='gh_pr_diff'



alias mylog='$EDITOR $HOME/mylog/worklog-$(date +%Y-%m-%d).md'
alias cublog='$EDITOR $HOME/cublog/worklog-$(date +%Y-%m-%d).md'
alias notion='open https://notion.so'
alias gpt='open https://chatgpt.com'
alias goo='open https://google.com'

alias arxivtotext='arxiv2text'

alias tj='tjournal'

# colorize
alias ip='ip -c=always'

# taskwarrior
alias tw='taskwarrior-tui'

# just
if command_exists just; then
    source <(just --completions zsh)
fi

alias ju='just'
alias jus='print -z "$(just.sh -j ./.user.justfile -d .)"'
alias ja='print -z "$(just.sh -j $HOME/.config/my-scripts/justfile -d .)"'
alias jc='ja'
alias jj='ja'
alias jg='ja'
alias j='print -z "$(just.sh -j ./justfile -d .)"'
alias jr='print -z "$(just.sh -j $MY_CUBRID/remote/justfile -d .)"'

####################
# Kubernetes Aliases
####################

alias mk='minikube kubectl --'
alias miku='minikube kubectl --'
alias minienv='eval $(minikube -p minikube docker-env)'

# alias kubectl='miku'
alias k='kubectl'
alias ku='k9s'

# Apply and Get Commands
alias ka='kubectl apply -Rf'                     # Apply recursively
alias kgp='kubectl get pods -o wide'              # Get pods with details
alias kgpa='kubectl get pods -o wide -A'          # Get all pods with details
alias kgpw='kubectl get pods -o wide -w'          # Watch pods with details
alias kgpaw='kubectl get pods -o wide -A -w'      # Watch all pods with details

alias kgd='kubectl get deploy -o wide'            # Get deployments with details
alias kgs='kubectl get svc -o wide'               # Get services with details
alias kgn='kubectl get nodes -o wide'             # Get nodes with details
alias kge='kubectl get events -w --field-selector type=Warning'  # Watch warnings
alias kgv='kubectl get pvc -o wide'               # Get persistent volume claims

# Create and Run Commands
alias kcrn='kubectl create deployment nginx --image=nginx'          # Create nginx deployment
alias krrn='kubectl run nginx --image=nginx --restart=Never'        # Run nginx pod
alias krb='kubectl run busybox --image=busybox --restart=Never -- sleep 1d'  # Run busybox pod

# Describe, Logs, and Exec Commands
alias kdp='kubectl describe pod'                 # Describe a pod
alias kdd='kubectl describe deploy'              # Describe a deployment
alias kds='kubectl describe svc'                 # Describe a service
alias kl='kubectl logs'                          # Show logs for a pod
alias klf='kubectl logs -f'                      # Follow logs for a pod
alias ke='kubectl exec -it'                      # Exec into a pod

# Namespace and Context Commands
alias kgns='kubectl get ns'                      # Get namespaces
alias kcn='kubectl config get-contexts'          # Get contexts
alias kus='kubectl config use-context'           # Switch context

# Common Utility Aliases
alias kdel='kubectl delete'                      # Delete resource
alias kdpw='watch kubectl get pods -o wide'      # Watch pods with details


# cgdb
cgdb-recent-core() {
    local core_file=$(/bin/ls -t core* 2>/dev/null | head -n 1)
    if [[ -z "$core_file" ]]; then
        echo "No core files found in the current directory."
        return 1
    fi

    # Extract the execfn field from the file command output
    local executable=$(file "$core_file" | grep -o "execfn: '[^']*" | cut -d"'" -f2)

    if [[ -z "$executable" ]]; then
        echo "Could not determine the executable for $core_file."
        return 1
    fi

    # Run gdb with the core file and the executable
    echo "Analyzing core file: $core_file with executable: $executable"
    cgdb "$executable" "$core_file"
}
alias crc='cgdb-recent-core'

forever() {
    args="$*"
    zellij action rename-tab $args
    while true; do
        # Execute the command entered by the user
        eval "$*"

        echo -n "Press Enter to rerun: $@"  # Optional: Prompt symbol
        read -r command
    done
}
alias jf='CMD=$(just --summary | tr " " "\n" | eval "$JUST_CHOOSER") && print -z "forever just $CMD"'
alias fo='forever'
alias f='forever'

alias na='print -z $(navi --print)'

# alias a='' #
alias b='btop'
alias bu='./build.sh'
# alias c <- cd
alias ca='cargo'
alias cm='cmake'
alias d='docker'
# alias e <- nvim
alias f='fd'
alias g='git'
# alias h <- --help
alias i='' # ip?
alias jo='journalctl'
alias k='kubectl'
alias kg='k gets'
alias kgp='kubectl get pods'
alias kgd='kubectl get deployments'
alias kgs='kubectl get services'
# alias l <- eza
alias m='man' # bat -l man -p
alias ma='make'
alias n='nix'
alias ol='ollama'
alias p='podman'
alias pa='pacman'
alias q='exit'
# alias r <- repeat
alias s='sudo systemctl'
alias t='tldr'
alias u='uv'
# alias v <- nvim
alias w='which'
alias wa='which -a'
alias wg='wget'
alias x='xargs' # xdg-open?
# alias y <- yazi
# alias z <- zoxide, zellij

alias battery="upower -e | fzf --preview='upower -i {}'"

# alias end
