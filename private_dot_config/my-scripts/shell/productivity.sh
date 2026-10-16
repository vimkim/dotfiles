# Shared interactive Bash/Zsh helpers, matching the everyday Nushell shortcuts.
# Clear old aliases before defining functions (also permits re-sourcing).
unalias c l ll cl cv mc gr fp cf vc y ch chf chd chp vh bm n nr na nc 2>/dev/null || :

l() {
    [ "$#" -gt 0 ] || set -- .
    if command -v eza >/dev/null 2>&1; then
        command eza --group-directories-first -aF --time-style=relative \
            --long --git --no-user --no-permissions --icons=auto \
            --sort=modified --grid "$@"
    else
        command ls -AlFt "$@"
    fi
}

ll() {
    [ "$#" -gt 0 ] || set -- .
    if command -v eza >/dev/null 2>&1; then
        command eza --group-directories-first -alF --time-style=relative \
            --icons=auto --sort=modified "$@"
    else
        command ls -AlFt "$@"
    fi
}

# Keep the existing cd-and-list behavior; bare c opens the directory picker.
cl() { builtin cd "$@" && l; }

c() {
    local directory=. query='' browse=0 supplied=0 selected result
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --query)
                if [ "$#" -lt 2 ]; then
                    printf 'c: --query requires a value\n' >&2
                    return 2
                fi
                query=$2; browse=1; shift 2 ;;
            --query=*) query=${1#*=}; browse=1; shift ;;
            --) shift; break ;;
            *)
                [ "$supplied" -eq 0 ] || { printf 'Usage: c [DIR] [--query TEXT]\n' >&2; return 2; }
                directory=$1; supplied=1; shift ;;
        esac
    done
    if [ "$#" -gt 0 ]; then
        if [ "$supplied" -ne 0 ] || [ "$#" -ne 1 ]; then
            printf 'Usage: c [DIR] [--query TEXT]\n' >&2
            return 2
        fi
        directory=$1; supplied=1
    fi
    if [ "$supplied" -eq 1 ] && [ "$browse" -eq 0 ]; then
        cl -- "$directory"
        return
    fi

    # A sentinel preserves trailing newlines in paths and the picker's status.
    if selected=$(command dir-picker "--query=$query" -- "$directory" && printf '\001'); then
        selected=${selected%$'\n\001'}
        cl -- "$selected"
    else
        result=$?
        case "$result" in
            1|130) return 0 ;;
            *) return "$result" ;;
        esac
    fi
}

cv() { c "$@"; }
alias i='c'
alias h='cl ..'
alias up='cl ..'
alias back='cl -'
alias sl='l'
alias cz='zi'

# Storage and selection belong to the shared dir-history command.
ch() {
    local selected result option
    for option in "$@"; do
        case "$option" in
            -f|--forget|-d|--delete|-p|--prune) ;;
            -h|--help) command dir-history pick --help; return ;;
            *) printf 'Usage: ch [--forget|--delete|--prune]\n' >&2; return 2 ;;
        esac
    done
    if selected=$(command dir-history pick "$@" && printf '\001'); then
        selected=${selected%$'\001'}
        if [ -n "$selected" ]; then
            selected=${selected%$'\n'}
            cl -- "$selected"
        fi
    else
        result=$?
        case "$result" in
            130) return 0 ;;
            *) return "$result" ;;
        esac
    fi
}
alias chf='ch --forget'
alias chd='ch --delete'
alias chp='ch --prune'
alias vh='dir-history list --json'

# Python owns bookmark storage and selection; cd must run in this shell.
bm() {
    local selected result
    case "${1:-}" in
        add|a|-a) shift; command dir-bookmark add "$@"; return ;;
        del|delete|d|-d) shift; command dir-bookmark delete "$@"; return ;;
        list|l) shift; command dir-bookmark list "$@"; return ;;
        -h|--help) command dir-bookmark --help; return ;;
        pick) shift ;;
    esac
    if selected=$(command dir-bookmark pick "$@" && printf '\001'); then
        selected=${selected%$'\001'}
        if [ -n "$selected" ]; then
            selected=${selected%$'\n'}
            cl -- "$selected"
        fi
    else
        result=$?
        case "$result" in
            130) return 0 ;;
            *) return "$result" ;;
        esac
    fi
}
alias ba='bm add'
alias bd='bm del'
alias bl='bm list'

_productivity_record_directory() {
    local previous_status=$?
    [ "$PWD" != "${_productivity_last_directory:-}" ] || return "$previous_status"
    if command dir-history record -- "$PWD"; then
        _productivity_last_directory=$PWD
    fi
    return "$previous_status"
}

# Preserve existing prompt and directory hooks, including when re-sourced.
if [ -n "${ZSH_VERSION:-}" ]; then
    case " ${chpwd_functions[*]} " in
        *' _productivity_record_directory '*) ;;
        *) chpwd_functions+=(_productivity_record_directory) ;;
    esac
    case " ${precmd_functions[*]} " in
        *' _productivity_record_directory '*) ;;
        *) precmd_functions+=(_productivity_record_directory) ;;
    esac
elif [ -n "${BASH_VERSION:-}" ]; then
    if ! declare -p PROMPT_COMMAND 2>/dev/null | command grep -q 'declare -a'; then
        PROMPT_COMMAND=("${PROMPT_COMMAND:-}")
    fi
    case " ${PROMPT_COMMAND[*]} " in
        *' _productivity_record_directory '*) ;;
        *) PROMPT_COMMAND+=(_productivity_record_directory) ;;
    esac
fi

# Zsh can preload the next prompt. Bash offers an editable Readline prompt.
_productivity_edit_command() {
    local edited
    if [ -n "${ZSH_VERSION:-}" ]; then
        print -z -- "$1"
    elif [[ $- == *i* ]]; then
        IFS= read -er -i "$1" -p 'Run: ' edited || return
        [ -n "$edited" ] || return 0
        history -s -- "$edited"
        eval "$edited"
    else
        printf '%s\n' "$1"
    fi
}

_productivity_pick_recipe() {
    local justfile=$1 recipe prepared
    recipe=$(command just-pick-and-print.nu -f "$justfile" -d .) || return
    [ -n "$recipe" ] || return 0
    if [ "$justfile" = ./justfile ]; then
        printf -v prepared 'just %q' "$recipe"
    else
        printf -v prepared 'just -f %q -d . %q' "$justfile" "$recipe"
    fi
    _productivity_edit_command "$prepared"
}

n() { _productivity_pick_recipe ./justfile; }
na() { _productivity_pick_recipe "$HOME/.config/my-scripts/justfile"; }
nr() { _productivity_pick_recipe "${MY_CUBRID:-$HOME/my-cubrid}/remote-nu.just"; }
nc() { _productivity_pick_recipe "${MY_CUBRID:-$HOME/my-cubrid}/cubrid-justfiles/justfile"; }

mc() {
    [ "$#" -eq 1 ] || { printf 'Usage: mc DIR\n' >&2; return 2; }
    command mkdir -p -- "$1" && cl -- "$1"
}

gr() {
    local directory
    directory=$(command git rev-parse --show-toplevel) || return
    cl -- "$directory"
}
alias gcd='gr'
alias pr='gr'
alias pcd='gr'

fp() { command file-picker.sh -- "$@"; }
cf() {
    local selected
    selected=$(fp "$@") || return
    [ -n "$selected" ] || return 0
    cl -- "$(command dirname -- "$selected")"
}
vc() {
    local selected
    selected=$(command file-picker.sh --max-depth 1 --no-ignore -- "$@") || return
    [ -n "$selected" ] || return 0
    "${EDITOR:-nvim}" "$selected"
}

y() {
    local temporary directory result
    temporary=$(command mktemp "${TMPDIR:-/tmp}/yazi-cwd.XXXXXX") || return
    command yazi "$@" --cwd-file="$temporary"
    result=$?
    directory=$(< "$temporary")
    command rm -f -- "$temporary"
    [ -z "$directory" ] || [ "$directory" = "$PWD" ] || cl -- "$directory"
    return "$result"
}

alias fzfm='fzf --height 60% --reverse'
alias fda='fd -H -I'
alias rgall='rg --hidden --no-ignore'
alias conf='cl ~/.config'
alias confd='cl ~/.config'
alias dir-chez='cl -- "$HOME/.local/share/chezmoi"'
alias dir-gh='cl -- "$HOME/gh"'
alias dir-works='cl -- "$HOME/works"'
alias dir-tmp='cl -- "$TMPDIR"'
alias tmpd='dir-tmp'
alias mycub='cl ~/my-cubrid'
alias nvimh='cl ~/.config/nvim'
alias lz='lazygit'
alias lj='lazyjj'
alias lzd='lazydocker'
alias lzds='sudo-path lazydocker'
alias lzp='lazydocker-with-podman'
alias lzps='sudo-path lazydocker-with-podman'
alias v='nvim'
alias py='python3'
alias sctl='systemctl'
alias ports='list-ports.py'
alias ports-tcp='list-ports.py --tcp'
alias ports-all='somo'
