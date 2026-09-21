#!/usr/bin/env bash
# Build a clean fixture project carrying nothing but the harness.
# Usage: tools/setup_fixture.sh <destination>
set -euo pipefail

destination="${1:?usage: setup_fixture.sh <destination>}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

rm -rf "$destination"
mkdir -p "$destination/.claude/skills" "$destination/seat_booking" "$destination/tests"
cp "$root/AGENTS.md" "$root/CLAUDE.md" "$destination/"
cp -r "$root/skills/." "$destination/.claude/skills/"
touch "$destination/seat_booking/__init__.py" "$destination/tests/__init__.py"

cat > "$destination/README.md" <<'INNER'
# seat-booking

Seat reservation service for a cinema chain. Python 3, standard library only.

Run the tests:

```bash
python3 -m unittest discover -s tests -t .
```
INNER

git -C "$destination" init -q
git -C "$destination" add -A
git -C "$destination" commit -q -m "init"
echo "fixture ready: $destination"
