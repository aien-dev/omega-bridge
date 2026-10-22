#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-only
# Local binary bootstrap only. No downloads, services, global packages or shell edits.
set -eu
binary=${1:?usage: sh install/bootstrap.sh /path/to/built/om}
exec "$binary" bootstrap
