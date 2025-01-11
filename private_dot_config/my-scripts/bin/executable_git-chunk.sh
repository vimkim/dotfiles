git diff | grep -E '^\+\+\+ |@@' | awk '
/^\+\+\+/ { file = $2; gsub("^b/", "", file); }
/^@@/ { print file, $0; }
' | awk -F' @@ ' '/@@/ {if (match($2, /\+[0-9]+,/)) {print $1, substr($2, RSTART+1, RLENGTH-2)}}'
