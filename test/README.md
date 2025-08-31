<!-- BEGIN: we-readme -->
# Development runner (we)

This project includes a Make block managed by the `we` tool.

Quick commands:

- make up         # start service (idempotent)
- make watch      # up (or restart if active) + follow
- make launch     # up (or restart if active) + logs (alias: run)
- make follow     # tail logs
- make logs       # show last N lines (TAIL=100)
- make down       # stop tracked unit
- make kill       # stop all we-<service>-* units for this user

RELOAD=1 enables live reload via watchexec; set RELOAD=0 to disable. Set SECURE=1 to enable systemd hardening flags.

Make output is quiet by default (only service output). Use `make VERBOSE=1 <target>` for full make chatter.

<!-- END: we-readme -->
