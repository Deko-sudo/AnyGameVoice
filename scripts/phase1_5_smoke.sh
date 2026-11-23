#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "${AGV_PYTHON:-python}" -B "$script_dir/phase1_5_smoke.py" "$@"
