"""Legacy entry point: the installed Dictate.app still launches this path.
Rebuild the app with scripts/build_app.sh and this file can be deleted."""

from dictate.menubar import main

main()
