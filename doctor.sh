#!/usr/bin/env bash
# Read-only dependency check. Run:  bash doctor.sh
exec bash "$(cd "$(dirname "$0")" && pwd)/skills/edit-video/setup/doctor.sh" "$@"
