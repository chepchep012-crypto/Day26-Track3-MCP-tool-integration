#!/usr/bin/env bash
# Launches MCP Inspector against this server.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p .npm-cache
NPM_CONFIG_CACHE="$PWD/.npm-cache" npx -y @modelcontextprotocol/inspector python mcp_server.py
