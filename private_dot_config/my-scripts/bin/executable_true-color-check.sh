#!/bin/bash

# Print a smooth RGB color gradient
awk -v term_cols="$(tput cols)" 'BEGIN{
    s="/\\";
    for (colnum = 0; colnum<term_cols; colnum++) {
        r = 255-(colnum*255/term_cols);
        g = (colnum*510/term_cols);
        b = (colnum*255/term_cols);
        if (g>255) g = 510-g;
        printf "\033[48;2;%d;%d;%dm", r,g,b;
        printf "\033[38;2;%d;%d;%dm", 255-r,255-g,255-b;
        printf "%s\033[0m", substr(s,colnum%2+1,1);
    }
    printf "\n";
}'

# Print color blocks with RGB values
for r in $(seq 0 127 255); do
    for g in $(seq 0 127 255); do
        for b in $(seq 0 127 255); do
            printf "\x1b[48;2;${r};${g};${b}m  \x1b[0m"
        done
        printf "\n"
    done
done

# Print test pattern
echo
echo "If you see smooth gradients above without banding, your terminal supports true color."
echo "You can also verify by running: echo \$COLORTERM"
