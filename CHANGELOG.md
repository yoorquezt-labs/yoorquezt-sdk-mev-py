# Changelog

All notable changes to the YoorQuezt MEV Python SDK.

## [Unreleased]

## [0.3.0] - 2026-03-10

### Added
- **Streaming tests**: 25 tests for SSE streaming, error events, and auth
- **WebSocket tests**: 23 tests for connection lifecycle, subscribe/unsubscribe
- **Error handling tests**: 43 tests covering `QMEVError`, `fromCode`, all 19 error codes
- **Web3 provider wrapper**: Drop-in provider for MEV protection

### Security
- Added `.env`, `.env.*` to `.gitignore`
- Pinned all dependencies: `httpx==0.27.2`, `websockets==13.1`, `pydantic==2.10.0`
- Pinned dev dependencies in `requirements-dev.txt`

## [0.2.0] - 2026-03-09

### Added
- Comprehensive test suite: 162 tests (unit, integration, smoke, E2E)
- Real testnet integration tests against live OFA proxy on Sepolia

## [0.1.0] - 2026-03-08

### Added
- Async MEV client with Pydantic models (78 tests)
- Full OFA endpoint coverage: rebates, audit, SLA, health
- WebSocket streaming support
