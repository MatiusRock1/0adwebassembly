# Evidence retained in Git

Keep result reports, acceptance summaries, parity results, manifests, hashes and
source patches. Representative screenshots cited in the documentation are
explicitly allowed by this directory's `.gitignore`.

Raw CPU profiles, symbols, state dumps, traces, repeated screenshots, logs and
per-frame CSV recordings are local diagnostic artifacts. They were removed from
the published branch history on 2026-10-27 to reduce its size. Historical reports
can still reference these local artifacts; their presence in a report does not
mean they remain downloadable from Git.

The original game assets are unaffected. Removing diagnostic artifacts does not
change the recorded acceptance status or turn a pending result into a pass.
