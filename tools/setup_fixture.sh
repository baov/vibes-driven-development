#!/usr/bin/env bash
# Build a clean fixture project carrying nothing but the harness.
# Usage: tools/setup_fixture.sh <destination>
#
# The destination is deleted and rebuilt, so the script only does that to a
# directory it created itself (it leaves a `.fixture` marker). Anything
# else that exists and is not empty is refused.
set -euo pipefail

destination="${1:?usage: setup_fixture.sh <destination>}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
harness="$root/harness"
marker=".fixture"

if [ -e "$destination" ]; then
  if [ ! -d "$destination" ]; then
    echo "setup_fixture: $destination exists and is not a directory" >&2
    exit 1
  fi
  resolved="$(cd "$destination" && pwd -P)"
  if [ "$resolved" = "$(pwd -P)" ] || [ "$resolved" = "$HOME" ] || [ "$resolved" = "/" ] \
     || [ "$resolved" = "$(cd "$root" && pwd -P)" ]; then
    echo "setup_fixture: refusing to rebuild $resolved" >&2
    exit 1
  fi
  if [ -n "$(ls -A "$destination")" ] && [ ! -f "$destination/$marker" ]; then
    echo "setup_fixture: $destination is not empty and was not created by this script" >&2
    exit 1
  fi
fi

rm -rf "$destination"
mkdir -p "$destination/.claude/skills" "$destination/seat_booking" "$destination/tests"
touch "$destination/$marker"
cp "$harness/AGENTS.md" "$harness/CLAUDE.md" "$destination/"
cp -r "$harness/skills/." "$destination/.claude/skills/"
touch "$destination/seat_booking/__init__.py" "$destination/tests/__init__.py"

cat > "$destination/README.md" <<'INNER'
# seat-booking

Seat reservation service for a cinema chain. Python 3, standard library only.

Run the tests:

```bash
python3 -m unittest discover -s tests -t .
```
INNER

# A fixture must not depend on the operator's git setup: identity, signing and
# hooks all come from the global config otherwise.
git -C "$destination" init -q
git -C "$destination" add -A
git -C "$destination" \
  -c user.name=fixture -c user.email=fixture@example.invalid \
  -c commit.gpgsign=false -c core.hooksPath=/dev/null \
  commit -q -m "init"
echo "fixture ready: $destination"
