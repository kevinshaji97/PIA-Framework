import json

import pytest
from click.testing import CliRunner

from pia import analysis, cli as cli_module, storage
from pia.analysis import analyse, evidence_in_text, parse_json
from pia.discovery import Candidate, _unwrap_redirect, rank_candidates, registrable_domain, vendor_domains
from pia.fetch import PolicyDocument, html_to_text, looks_like_policy
from pia.providers import LLMError, detect_provider, get_provider
from pia.rubric import CRITERIA, MAX_SCORE, grade, score

POLICY = (
    "Acme Privacy Policy. Last updated 1 January 2026. This privacy policy explains how Acme handles "
    "personal data. We collect your email address and IP address to provide the service. "
    "We use personal data only to operate and secure the service. We do not sell personal data. "
    "We share data with service providers under contract. We retain logs for 30 days. "
    "You may access, correct, delete or export your data by emailing privacy@acme.test. "
    "Data is encrypted in transit and at rest. Transfers outside the EEA rely on Standard Contractual Clauses. "
) * 8


class FakeProvider:
    name, model = "fake", "fake-1"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def complete(self, system, user):
        self.calls += 1
        return self.replies.pop(0)


def best_reply(**overrides):
    criteria = {c.key: {"rating": max(c.options, key=lambda r: c.options[r][0]),
                        "evidence": "We do not sell personal data.", "rationale": "r"} for c in CRITERIA}
    criteria.update(overrides)
    return json.dumps({
        "policy_owner": "Acme", "applies_to_dependency": True, "policy_last_updated": "2026-01-01",
        "summary": "Fine.", "data_collected": ["email address", "IP address"], "criteria": criteria,
    })


def doc():
    return PolicyDocument("https://acme.test/privacy", "Privacy", POLICY)


# --- rubric ---

def test_weights_sum_to_ten():
    assert MAX_SCORE == 10


def test_best_and_worst_scores():
    best = {c.key: max(c.options, key=lambda r: c.options[r][0]) for c in CRITERIA}
    assert score(best)[0] == 10
    assert score({})[0] == 0  # everything not_stated


def test_no_personal_data_scores_full_marks():
    assert score({"data_minimisation": "none"})[0] == 10


def test_grade_bands():
    assert [grade(x) for x in (9, 6.5, 4, 1)] == ["Strong", "Adequate", "Weak", "Poor"]


# --- analysis ---

def test_parse_json_handles_fences_and_prose():
    assert parse_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Result: {"a": {"b": 2}} done') == {"a": {"b": 2}}
    with pytest.raises(ValueError):
        parse_json("no json here")


def test_evidence_verification():
    assert evidence_in_text("We do not sell personal data", POLICY)
    assert evidence_in_text("“We retain logs for 30 days.”", POLICY)
    assert evidence_in_text("We collect your email address ... to provide the service", POLICY)
    assert not evidence_in_text("We sell personal data to advertisers", POLICY)


def test_analyse_scores_and_verifies():
    a = analyse("acme-sdk", "1.0.0", doc(), FakeProvider([best_reply()]))
    assert a.score == 10 and a.grade == "Strong"
    assert all(c.evidence_verified for c in a.criteria)
    assert a.warnings == []


def test_invalid_rating_and_fabricated_evidence_are_flagged():
    reply = best_reply(data_minimisation={"rating": "minimal", "evidence": "", "rationale": ""},
                       retention={"rating": "forever-ish", "evidence": "", "rationale": ""},
                       security={"rating": "specific", "evidence": "We are ISO 27001 certified", "rationale": ""})
    a = analyse("acme-sdk", "1.0.0", doc(), FakeProvider([reply]))
    assert a.score == 8.5  # 10 - 0.5 (minimal collection) - 1 (invalid retention -> not_stated)
    assert any("invalid rating" in w for w in a.warnings)
    assert any("security" in w and "verbatim" in w for w in a.warnings)


def test_analyse_retries_bad_json_then_fails():
    provider = FakeProvider(["oops", best_reply()])
    assert analyse("x", "1", doc(), provider).score == 10 and provider.calls == 2
    with pytest.raises(LLMError):
        analyse("x", "1", doc(), FakeProvider(["oops", "still not json"]))


def test_prompt_lists_every_criterion_and_option():
    prompt = analysis.build_prompt("acme", "1.0", doc())
    for c in CRITERIA:
        assert f'"{c.key}"' in prompt
        for rating in c.options:
            assert f'"{rating}"' in prompt


# --- discovery / fetch ---

def test_registrable_domain_and_vendor_domains():
    assert registrable_domain("docs.sentry.io") == "sentry.io"
    assert registrable_domain("www.bbc.co.uk") == "bbc.co.uk"
    assert vendor_domains(["https://github.com/getsentry/sentry-python", "https://docs.sentry.io/"]) == ["sentry.io"]


def test_rank_prefers_vendor_policy_over_code_hosts_and_forums():
    candidates = [
        Candidate("https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement", "GitHub Privacy"),
        Candidate("https://www.reddit.com/r/privacy/comments/x", "sentry privacy?"),
        Candidate("https://sentry.io/about/", "About"),
        Candidate("https://sentry.io/privacy/", "Privacy Policy | Sentry"),
    ]
    ranked = rank_candidates(candidates, "sentry-sdk", ["sentry.io"])
    assert ranked[0].url == "https://sentry.io/privacy/"
    assert all("github.com" not in c.url and "reddit.com" not in c.url for c in ranked)


def test_unwrap_duckduckgo_redirects():
    assert _unwrap_redirect("//duckduckgo.com/l/?uddg=https%3A%2F%2Facme.test%2Fprivacy&rut=x") == "https://acme.test/privacy"
    assert _unwrap_redirect("https://duckduckgo.com/y.js?ad_provider=x") is None
    assert _unwrap_redirect("https://acme.test/privacy") == "https://acme.test/privacy"


def test_html_to_text_strips_chrome():
    html = f"<html><head><title>Privacy</title><script>x()</script></head><body><nav>Menu</nav>" \
           f"<main><h1>Policy</h1><p>{POLICY}</p></main><footer>Footer</footer></body></html>"
    title, text = html_to_text(html)
    assert title == "Privacy"
    assert "Menu" not in text and "Footer" not in text and "x()" not in text
    assert looks_like_policy(text)


# --- providers ---

def test_provider_detection_and_key_errors(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert detect_provider() is None
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assert detect_provider() == "gemini"
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        get_provider("anthropic")
    with pytest.raises(LLMError, match="--base-url"):
        get_provider("openai-compatible", model="m")


# --- storage + CLI ---

def test_cli_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("PIA_DB", str(tmp_path / "pia.db"))
    policy = tmp_path / "policy.txt"
    policy.write_text(POLICY)
    monkeypatch.setattr(cli_module, "get_provider", lambda *a, **k: FakeProvider([best_reply()]))

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["assess", "acme-sdk==1.2.3", "--provider", "openai",
                                            "--ecosystem", "none", "--policy-file", str(policy), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert (data["dependency"], data["version"], data["score"]) == ("acme-sdk", "1.2.3", 10)

    assert storage.load(1).score == 10
    listing = runner.invoke(cli_module.cli, ["history"])
    assert "acme-sdk" in listing.output

    gated = runner.invoke(cli_module.cli, ["assess", "acme-sdk", "1.2.3", "--provider", "openai",
                                           "--ecosystem", "none", "--policy-file", str(policy),
                                           "--no-save", "--fail-under", "11"])
    assert gated.exit_code == 1


def test_cli_requires_version():
    result = CliRunner().invoke(cli_module.cli, ["assess", "acme-sdk"])
    assert result.exit_code == 2 and "version" in result.output.lower()


# --- .env loading and manual policy fallback ---

def test_env_file_loaded_without_overriding_real_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / ".env").write_text("PIA_TEST_KEY=from-file\nPIA_TEST_SHELL=from-file\n")
    monkeypatch.delenv("PIA_TEST_KEY", raising=False)
    monkeypatch.setenv("PIA_TEST_SHELL", "from-shell")
    cli_module.load_env_files()
    import os
    assert os.environ["PIA_TEST_KEY"] == "from-file"
    assert os.environ["PIA_TEST_SHELL"] == "from-shell"
    monkeypatch.delenv("PIA_TEST_KEY")


def _search_fails(*args, **kwargs):
    raise cli_module.PolicyNotFound("No privacy policy candidates found for 'acme-sdk'")


def _run_with_search_failure(monkeypatch, tmp_path, interactive, user_input=None):
    monkeypatch.setenv("PIA_DB", str(tmp_path / "pia.db"))
    monkeypatch.setattr(cli_module, "locate_policy", _search_fails)
    monkeypatch.setattr(cli_module, "is_interactive", lambda: interactive)
    monkeypatch.setattr(cli_module, "get_provider", lambda *a, **k: FakeProvider([best_reply()]))
    return CliRunner().invoke(cli_module.cli, ["assess", "acme-sdk", "1.0", "--provider", "openai",
                                               "--ecosystem", "none", "--no-save", "--json"], input=user_input)


def test_non_interactive_failure_explains_manual_option(monkeypatch, tmp_path):
    result = _run_with_search_failure(monkeypatch, tmp_path, interactive=False)
    assert result.exit_code == 1
    assert "--policy-url" in result.output and "pia assess acme-sdk 1.0" in result.output


def test_interactive_prompt_retries_until_policy_supplied(monkeypatch, tmp_path):
    policy = tmp_path / "policy.txt"
    policy.write_text(POLICY)
    stub = tmp_path / "stub.txt"
    stub.write_text("Just a landing page.")

    def failing_fetch(url, max_chars):
        raise cli_module.FetchError(f"Could not fetch {url}")
    monkeypatch.setattr(cli_module, "fetch_policy", failing_fetch)

    # bad URL -> retry; non-policy file -> decline; real policy file -> accepted
    result = _run_with_search_failure(monkeypatch, tmp_path, interactive=True,
                                      user_input=f"acme.test/privacy\n{stub}\nn\n{policy}\n")
    assert result.exit_code == 0, result.output
    assert "Could not fetch https://acme.test/privacy" in result.output
    assert json.loads(result.stdout[result.stdout.index("{"):])["score"] == 10


def test_interactive_prompt_blank_aborts(monkeypatch, tmp_path):
    result = _run_with_search_failure(monkeypatch, tmp_path, interactive=True, user_input="\n")
    assert result.exit_code == 1 and "Aborted" in result.output
