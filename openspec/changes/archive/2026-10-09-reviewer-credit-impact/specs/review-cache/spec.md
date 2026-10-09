# review-cache Specification

## Purpose

Committed JSONL cache so the reviewer reproduces offline and spend is bounded.

## ADDED Requirements

### Requirement: Cache key
The key MUST be sha256 over model, prompt version, system-prompt sha, payload and attempt. PFC variants and the adversarial set MUST yield distinct keys.

#### Scenario: Key sensitivity
- Given two requests differing in only one key component (including PFC on/off payload)
- Then their keys differ

### Requirement: Hit without key
A cache hit MUST work with no `OPENAI_API_KEY` set.

#### Scenario: Offline run
- Given a fully populated cache and no key
- When `python -m fundo review` runs
- Then it succeeds and makes no network call

### Requirement: Loud miss
A miss without a key MUST fail with a nonzero exit code and an error stating the miss count. It MUST NOT silently fall back to legacy labels.

#### Scenario: Missing entries
- Given a cache lacking 3 required keys and no API key
- When review runs
- Then exit code is nonzero and the message reports 3 misses

### Requirement: Append and flush before use
Each live response MUST be appended to the cache file and flushed before the response is used. `--refresh` MUST force live calls.

#### Scenario: Crash after a call
- Given a live call whose processing then raises
- Then the response is already present in the cache file

### Requirement: Spend estimate
Spend MUST be estimated from usage recorded in cached entries and MUST be below $10; a test MUST assert this.

#### Scenario: Budget
- Given the committed cache
- When spend is estimated
- Then it is < $10
