#!/bin/bash

fps() {
    local pid
    if [ "$UID" != "0" ]; then
        # pid=$(ps -f -u $UID | sed 1d | fzf -m | awk '{print $2}')
        pid=$(procs --color=always | sed '1,2d' | fzf -m --ansi --no-sort --reverse --height 60% | awk '{print $1}')
    else
        # pid=$(ps -ef | sed 1d | fzf -m | awk '{print $2}')
        pid=$(procs --color=always | sed '1,2d' | fzf -m --ansi | awk '{print $1}')
    fi

    if [ "x$pid" != "x" ]
    then
        procs --color=always $pid >&2
        echo $pid
    fi
}
fps
