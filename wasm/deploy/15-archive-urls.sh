#!/bin/sh
set -eu

# The browser reads each archive straight from its own HTTPS URL, which must
# allow this site with CORS. No query strings or HTML/sed metacharacters.
check_url() {
  case "$2" in
    *[!a-zA-Z0-9:/._-]*) echo "Invalid $1" >&2; exit 1 ;;
  esac
  case "$2" in
    https://?*) ;;
    *) echo "$1 must be an HTTPS URL" >&2; exit 1 ;;
  esac
}
: "${PUBLIC_ARCHIVE_URL:?Set PUBLIC_ARCHIVE_URL in the container environment}"
: "${MOD_ARCHIVE_URL:?Set MOD_ARCHIVE_URL in the container environment}"
check_url PUBLIC_ARCHIVE_URL "$PUBLIC_ARCHIVE_URL"
check_url MOD_ARCHIVE_URL "$MOD_ARCHIVE_URL"
# The launcher's per-archive URLs win over ?assets=, so /play/ finds the
# archives however it is opened (landing link, bookmarks, stale links).
for page in /usr/share/nginx/html/play/application.html /usr/share/nginx/html/play/index.html; do
  grep -q '<meta name="archive-public" content="[^"]*">' "$page" &&
    grep -q '<meta name="archive-mod" content="[^"]*">' "$page" ||
    { echo "$page has no archive URL placeholders; rebuild the package" >&2; exit 1; }
  sed -i -e "s|<meta name=\"archive-public\" content=\"[^\"]*\">|<meta name=\"archive-public\" content=\"$PUBLIC_ARCHIVE_URL\">|" \
    -e "s|<meta name=\"archive-mod\" content=\"[^\"]*\">|<meta name=\"archive-mod\" content=\"$MOD_ARCHIVE_URL\">|" "$page"
done
