# Forge Skills — distilled reusable knowledge (keep small, high-signal)

## nemotron-tokenfactory-endpoint
- when this applies: any generation/reasoning sub-call from Forge harness
- rule: use OpenAI-compatible client with base_url=https://api.tokenfactory.nebius.com/v1, model=nvidia/nemotron-3-super-120b-a12b, api_key from NEBIUS_API_KEY env var
- reason: Token Factory only serves Nemotron via OpenAI-compatible endpoint; default OpenAI URL/model silently bills wrong model

## sandbox-verify-before-claim
- when this applies: every coding task before diagnosis
- rule: run via sys.executable -I in isolated tmp workdir, 30s timeout, capture stdout+stderr, read actual output
- reason: memory shortcuts diagnosis, never verification
