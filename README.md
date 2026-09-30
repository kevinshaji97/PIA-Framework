# PIA Framework

Privacy Impact Assessment for third-party dependencies. Give it a dependency name and version;
it finds the vendor's privacy policy on the web, has the LLM of your choice classify the policy's
data collection and processing practices, and scores it **out of 10 (10 = most privacy-protective)**.

## Install

```bash
git clone https://github.com/kevinshaji97/PIA-Framework.git
cd PIA-Framework
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[all]"        # or ".[anthropic]" / ".[openai]" for just one SDK
```

## Configure your API key

Copy the example file and fill in the key for the provider you want to use:

```bash
cp .env.example .env
```

```ini
ANTHROPIC_API_KEY=sk-ant-...
```

`.env` is read from the current directory, then from `~/.pia/.env` (handy when running `pia` from
anywhere). Variables already exported in your shell take precedence. `.env` is git-ignored; never commit it.

## Usage

```bash
pia assess sentry-sdk 2.19.0
pia assess mixpanel-browser@2.58.0            # npm style
pia assess posthog==3.7.0 --json              # machine-readable output
pia history                                    # past assessments
pia show 3                                     # full report for assessment #3
```

Without installing: `python main.py assess sentry-sdk 2.19.0`.

### Supplying the policy manually

Web search can fail: the vendor may have no findable policy, or the search engine may rate-limit you.
You can always specify the policy yourself:

```bash
pia assess acme-sdk 1.4.0 --policy-url https://acme.example/legal/privacy   # skip the search entirely
pia assess acme-sdk 1.4.0 --policy-file ./acme-privacy.txt                  # local .txt / .html file
```

When run in a terminal, a failed search instead prompts you for a URL or file path. It re-prompts
if the URL can't be fetched and asks for confirmation if the page doesn't look like a privacy policy.
Press Enter on an empty line to abort. In scripts and CI (no terminal) it exits with an error showing the
`--policy-url` command to run.

## Choosing an LLM

The provider is picked from whichever API key is set, or explicitly with `--provider`
(also `PIA_PROVIDER` / `PIA_MODEL` / `PIA_BASE_URL` environment variables).

| `--provider`        | Key variable        | Default model       | Notes |
|---------------------|---------------------|---------------------|-------|
| `anthropic`         | `ANTHROPIC_API_KEY` | `claude-sonnet-5-5` | |
| `openai`            | `OPENAI_API_KEY`    | `gpt-4.1-mini`      | |
| `gemini`            | `GEMINI_API_KEY`    | `gemini-2.5-flash`  | via Gemini's OpenAI-compatible API |
| `ollama`            | none                | `llama3.1`          | local; policy text never leaves your machine |
| `openai-compatible` | `OPENAI_API_KEY` (optional) | set `--model` | any OpenAI-compatible server: `--base-url` required (LM Studio, vLLM, OpenRouter, Groq, ...) |

Override the model with `--model`. Policies can be long (up to `--max-chars`, default 100,000
characters ≈ 25k tokens), so local models need a large enough context window; for Ollama raise
`num_ctx` or lower `--max-chars`.

## How it works

1. **Registry lookup**: PyPI / npm (`--ecosystem`) confirms the version exists and gives the vendor's homepage.
2. **Policy discovery**: privacy links on the vendor homepage, plus a web search (Brave, falling back
   to DuckDuckGo). Candidates are ranked, and GitHub/forum/doc pages are penalised. The first page that
   reads like a real privacy policy is used.
3. **LLM classification**: the model rates each criterion from a fixed set of options and quotes
   the policy as evidence. Quotes that do not appear in the policy are flagged `[unverified]`.
4. **Deterministic scoring**: the score is computed in code from the ratings
   ([pia/rubric.py](pia/rubric.py)), so it is reproducible and does not depend on the model inventing a number.

| Criterion | Weight |
|---|---|
| Data collection scope | 2.0 |
| Sensitive data | 1.5 |
| Purpose of processing | 1.5 |
| Third-party sharing | 1.5 |
| Data retention | 1.0 |
| User rights | 1.0 |
| Consent and control | 0.5 |
| Security measures | 0.5 |
| International transfers | 0.5 |

Anything the policy does not address scores 0. If the policy states no personal data is collected
at all, the dependency scores 10. Grades: **Strong** ≥ 8, **Adequate** ≥ 6, **Weak** ≥ 4, **Poor** < 4.

Use `--fail-under 6` in CI to fail a build when a dependency scores below a threshold.

## Limitations

- A PIA score is only as good as the policy found. Always check the policy URL in the report.
  Pure open-source libraries that send no data anywhere usually have no privacy policy; if a
  publisher's website policy is picked up instead, the report warns that it may not apply.
- The policy describes the vendor's stated practices, not what the SDK actually transmits.
- Search engines rate-limit scripted queries; if discovery fails, pass `--policy-url`.
- The score is an automated aid to a privacy review, not legal advice.
- The policy text (a public document) is sent to the LLM provider you choose. Use `--provider ollama`
  to keep everything local.

History is stored in `~/.pia/assessments.db` (override with `PIA_DB`).

## Tests

```bash
pip install -e ".[dev]" && pytest
```
