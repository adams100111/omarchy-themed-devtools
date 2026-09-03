add_newline = true
command_timeout = 200
format = "[$directory$git_branch$git_status]($style)$character"
palette = "omarchy"

[palettes.omarchy]
signal = "{{ accent }}"
fg = "{{ foreground }}"
alert = "{{ red }}"

[character]
error_symbol = "[✗](bold alert)"
success_symbol = "[❯](bold signal)"

[directory]
truncation_length = 2
truncation_symbol = "…/"
repo_root_style = "bold signal"
repo_root_format = "[$repo_root]($repo_root_style)[$path]($style)[$read_only]($read_only_style) "

[git_branch]
format = "[$branch]($style) "
style = "italic signal"

[git_status]
format     = '[$all_status]($style)'
style      = "signal"
ahead      = "⇡${count} "
diverged   = "⇕⇡${ahead_count}⇣${behind_count} "
behind     = "⇣${count} "
conflicted = " "
up_to_date = " "
untracked  = "? "
modified   = " "
stashed    = ""
staged     = ""
renamed    = ""
deleted    = ""
