"""Remote (HTTP + OAuth) transport for the Google Analytics MCP server.

Importing this package installs the credential seam so that the unchanged
upstream tools use the per-request user's Google credentials.
"""

from analytics_mcp.remote import credentials

credentials.apply_patch()
