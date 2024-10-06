# alias begin

export EDITOR='nvim'
export CHEZ_EDITOR='chezmoi edit --watch'

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

# System aliases
alias rm='rm -i'

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
    export MANPAGER="sh -c 'col -bx | bat -l man -p'"
fi

# Conditionally set alias for `broot`
if command_exists broot; then
    alias tree='broot'
fi

if command_exists delta; then
    alias diff='delta'
    source <(delta --generate-completion zsh)
elif command_exists difft; then
    alias diff='difft --color=always'
fi

if [ -x "$(command -v eza)" ]; then

    export EZA_COMMON_OPTIONS='--group-directories-first --icons -aF'
    export EZA_LONG_OPTIONS='--long --git -ahF --grid --group-directories-first --color=always'
    alias ls="eza $EZA_COMMON_OPTIONS --icons"
    alias l='ls'
    alias la='ls'
    alias ll="eza --no-user --no-permissions $EZA_LONG_OPTIONS --icons"
    alias llsz="ll --total-size"
    alias lll="eza $EZA_LONG_OPTIONS --inode | less -RFiX" # no icons since modern less -r usage not recommended
elif [ -x "$(command -v lsd)" ]; then
    alias ls='lsd -aF'
    alias l='lsd -aF'
    alias la='lsd -laF'
    alias ll='lsd -laF'
    alias llg='lsd -laF --git'
fi

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

alias lzd='lazydocker'

alias sl='ls'

alias lz='lazygit'
alias lg='lazygit'

alias which="which -a"
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
alias vv='FILE=$(fd . -H -I --type f --max-depth 1 | fzf --height 40% --reverse) && [[ -n $FILE ]] && $EDITOR "$FILE"'
alias vx='FILE=$(fd . -H --type f | fzf --height 40% --reverse) && [[ -n $FILE ]] && $EDITOR "$FILE"'

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
    builtin cd "$@" && ls
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
alias cr='DIR=$(dirs -v | head -n 20 | awk '\''{print $2}'\'' | fzf --height 40% --reverse) && [[ -n $DIR ]] && eval cd "$DIR"'

# in order to include ".." to the selection list supplied to fzf, use $dirs
cv() {
    # Combine the parent directory and subdirectories into an array
    local dirs=("../" $(fd --max-depth 1 -H -I --type d --strip-cwd-prefix))
    # Pass the array to fzf for selection
    local dir=$(printf "%s\n" "${dirs[@]}" | fzf --height 40% --reverse)
    # If a directory was selected, change to that directory
    [[ -n $dir ]] && cd "$dir"
}
alias c='cv'

alias cb='cd ..'

alias cx='DIR=$(fd . -H -I --type d | fzf --height 40% --reverse) && [[ -n $DIR ]] && cd "$DIR"'
alias cxh='DIR=$(fd . -H -I --type d $HOME | fzf) && [[ -n $DIR ]] && cd "$DIR"'
alias cxg='DIR=$(fd . -H -I --type d $(relative_gitdir) | fzf) && [[ -n $DIR ]] && cd "$DIR"'

alias cf='cd "$(fd . -H --type f | fzf --height 40% --reverse | xargs -I {} dirname {})"'
alias cfh='cd "$(fd . -H --type f $HOME | fzf --height 40% --reverse | xargs -I {} dirname {})"'
alias cfg='cd "$(fd . -H --type f $(relative_gitdir) | fzf --height 40% --reverse | xargs -I {} dirname {})"'

alias ff='vxg'

alias gcd='cd $(relative_gitdir 2>/dev/null || echo ".")'
alias cdg='gcd'
alias pcd='gcd'
alias cdw='gcd'

alias up='cd ..'                                            # Move up one directory
alias back='cd $OLDPWD'                                    # Return to the previous directory

## Networking and System Information
alias ports='netstat -tulanp'
alias ipinfo='curl ipinfo.io' # Quick IP address and network info
alias myip='curl http://ipecho.net/plain' # External IP address

# Git Aliases
# alias ga='git add'
alias gc='git commit'
alias gcm='git commit -m'
alias gcv='git commit --verbose'
alias git_checkout_child='git checkout $(git log --all --ancestry-path ^HEAD --format=format:%H | tail -n 1)'
alias gup='git_checkout_child'
alias gdown='git checkout HEAD~1'
alias grs='git reset'

export MY_SCRIPTS="$HOME/.config/my-scripts"
alias rfv='$MY_SCRIPTS/rfv.sh'
alias frf='$MY_SCRIPTS/frf.sh'

git_log_fzf() {
    git log --oneline --graph --decorate | fzf | awk '{print $2}'
}
alias glf='git_log_fzf'

git_blame_file() {
    git log -1 --format="$@:%C(green)%Creset %C(red)%h%Creset %C(yellow)%ai%Creset %C(cyan)%an%Creset %C(white)%s%Creset" -- $@
}
alias gbf='git_blame_file'

git_blame_directory() {
    for file in "$1"/*; do
        git log -1 --format="$file:%C(green)%Creset %C(red)%h%Creset %C(yellow)%ai%Creset %C(cyan)%an%Creset %C(white)%s%Creset" -- "$file"
    done
}
alias gbd='git_blame_directory'

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
alias gg='git-graph'
export GIT_PRETTY_FORMAT='%C(auto)%h %C(blue)%an%C(reset) %C(magenta)%as%C(reset)%C(auto)%d %s %C(black)%C(bold)%cr%reset'
gl() {
    GIT_PAGER="less -iRFSX" \
        git log --graph --color \
        --pretty=format:"$GIT_PRETTY_FORMAT"
}

# Function to show all branches with git log
gloga() {
    GIT_PAGER="less -iRFSX" \
        git log --graph --color --all \
        --pretty=format:"$GIT_PRETTY_FORMAT"
}
alias gla='gloga'
alias glh='gl HEAD' # useful when followed by a branch like develop
alias gld='gl develop HEAD'

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
alias gs='git status'
alias gst='git status'

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

## git etc
alias gcz="~/.local/bin/cz"
alias gfz="git fuzzy"

# Deveplopment and Programming aliases

## python
alias py='python'

run_project() {
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
    elif [ -f CMakeLists.txt ]; then
        echo "Detected CMake project."
        cmake . && make
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
alias x='run_project'

test_project() {
    if [ -f Cargo.toml ]; then
        echo "Detected Rust project."
        cargo test
    else
        echo "No recognized project files found. Please add a specific case to the script."
    fi
}
alias xt='test_project'

configure_project() {
    if [ -f CMakePresets.json ]; then
        cmake --preset debug
    fi
}
alias confp='configure_project'

build_project() {
    if [ -f CMakePresets.json ]; then
        cmake --build --prese debug
    fi
}
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

## wsl aliases
if [ -x "$(command -v wslpath)" ]; then
    alias wh="cd $(wslpath $(cmd.exe /C "echo %USERPROFILE%" 2>/dev/null | tr -d '\r'))"
    alias ws="webstorm64.exe"
    alias ii="explorer.exe"
    alias open="explorer.exe"
fi

# init setup

## chezmoi
alias chz='chezmoi'
alias chez='chezmoi'
alias che='chezmoi edit --watch'
alias cheze='chezmoi edit --watch'
alias chzd='cd ~/.local/share/chezmoi'
alias chzh='cd ~/.local/share/chezmoi'
alias chezd='cd ~/.local/share/chezmoi'
alias chezh='cd ~/.local/share/chezmoi'
alias chezcd='cd ~/.local/share/chezmoi'
alias conf='chezd && chezmoi edit --apply'

## conf
alias confd='cd ~/.config && echo "prefer using chezmoi edit"'

source ~/my-cubrid/aliases.sh

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


function yy() {
    local tmp="$(mktemp -t "yazi-cwd.XXXXXX")"
    yazi "$@" --cwd-file="$tmp"
    if cwd="$(cat -- "$tmp")" && [ -n "$cwd" ] && [ "$cwd" != "$PWD" ]; then
        cd -- "$cwd"
    fi
    rm -f -- "$tmp"
}
alias y='yy'


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
alias notion='open https://notion.so'
alias gpt='open https://chatgpt.com'
alias goo='open https://google.com'

alias arxivtotext='arxiv2text'

# alias end
