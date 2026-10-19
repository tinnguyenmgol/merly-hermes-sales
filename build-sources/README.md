# Verified upstream source, bundled for reliable builds

Archive: hermes-agent-848fc0ad8be766b9dc10fe42bd80b5fc2d45d95c.tar.gz
Upstream: https://github.com/NousResearch/hermes-agent
Original URL: https://codeload.github.com/NousResearch/hermes-agent/tar.gz/848fc0ad8be766b9dc10fe42bd80b5fc2d45d95c
SHA-256: 1e4d70199e9153b1a202f73d37c9316831b3df9b77a7449487d78fdbeeb922a7
Size: 83,630,150 bytes. Full, unmodified upstream archive, including its license.

This is a byte-identical copy of the previously verified public source archive,
not a reconstructed tar, credential, binary runtime image or modified upstream.
The pin/checksum in HERMES-SOURCE.json remains unchanged. Before bundling, the
cached original archive was hashed again. VPS downloads from codeload returned429
on all5 attempts; raising retry counts alone does not solve that dependency.

Docker now COPYs this archive before extraction. fetch_hermes.py CLI requires the
local bundle, checks size/SHA-256, and stages path-filtered extraction. Missing or
corrupt files fail explicitly; there is NO network fallback in the build CLI.
An explicit developer function call can still use bounded network download for
maintenance, but Docker's entrypoint does not select that path.

Tradeoff: Git repository/clone increases by about84MB. Keep the archive binary;
do not recompress it or silently update checksums to accept different bytes.
Review any future upstream pin/source/license update separately.

Verified in Workspace: full extraction entrypoint with urllib network forbidden;
fresh Python3.14.8 venv, editable install with the exact mcp/web extras and pinned
aiohttp3.14.3/gunicorn26.2.0; all95 tests pass in that fresh environment. This is
not a complete Docker image build or deployed runtime/model acceptance.

Only upstream SOURCE extraction is offline. Pulling the base image, cloning this
repo and installing Python dependencies still need their respective networks.
No secrets are needed at build time; runtime keys should not be Build-time envs.
