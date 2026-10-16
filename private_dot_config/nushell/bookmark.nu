# Shell adapter for the shared Python dir-bookmark command.
def _dir_bookmark_output [args: list<string>] {
  let result = (^dir-bookmark ...$args | complete)
  if $result.exit_code == 130 and $args.0 == "pick" { return "null" }
  if $result.exit_code != 0 {
    error make {msg: ($result.stderr | str trim)}
  }
  if ($result.stderr | is-not-empty) { print -e ($result.stderr | str trim) }
  $result.stdout
}

def --env --wrapped bm [...args: string] {
  let operation = if ($args | is-empty) { "" } else { $args.0 }
  let rest = ($args | skip 1)
  match $operation {
    "add" | "a" | "-a" => { ^dir-bookmark add ...$rest }
    "del" | "delete" | "d" | "-d" => { ^dir-bookmark delete ...$rest }
    "list" | "l" => { _dir_bookmark_output (["list" "--json"] ++ $rest) | from json }
    "-h" | "--help" => { ^dir-bookmark --help }
    _ => {
      let selection_args = if $operation == "pick" { $rest } else { $args }
      let selected = (_dir_bookmark_output (["pick" "--json"] ++ $selection_args) | from json)
      if $selected != null { cl $selected }
    }
  }
}
