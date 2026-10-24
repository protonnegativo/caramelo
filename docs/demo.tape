# README demo, recorded with VHS: https://github.com/charmbracelet/vhs
#
# VHS opens a real terminal, types these commands and records the screen, so the GIF shows exactly what
# a user sees. Run it from the repository root on Linux or macOS (needs vhs, ttyd, ffmpeg and pipx):
#
#     vhs docs/demo.tape
#
# The searches hit the real sites, so results and timings change from one recording to the next.
#
# Then fast-forward the waits (install, progress bar, silent search). Find the time ranges by watching the
# GIF; these matched the current recording:
#
#     python scripts/speedup_gif.py docs/demo.gif docs/demo.gif \
#         --wait 3.1-13.88:8 --wait 18.4-37.3:6 --wait 43.4-56.6:10 --hold-end 1.5

Output docs/demo.gif

Require pipx

Set Shell "bash"
Set FontSize 15
Set Width 1320
Set Height 900
Set Padding 20
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set TypingSpeed 45ms

# Off camera: remove any previous install, so the recording shows a real first install.
Hide
Type "pipx uninstall caramelo-osint >/dev/null 2>&1; clear"
Enter
Sleep 3s
Show

# 1. Install
Type "pipx install git+https://github.com/protonnegativo/caramelo"
Sleep 500ms
Enter
Wait@5m
Sleep 2s
Type "clear"
Enter
Sleep 500ms

# 2. Search: banner, progress bar and the dossier
Type "caramelo johndoe -c social -c gaming"
Sleep 500ms
Enter
Wait+Screen@5m /Dossier: johndoe/
Wait@1m
Sleep 6s
Type "clear"
Enter
Sleep 500ms

# 3. Silent mode: one "site<TAB>url" line per profile, for scripts and pipes
Type "caramelo johndoe --silent -c music -c video --no-pivot"
Sleep 500ms
Enter
Wait@5m
Sleep 5s
