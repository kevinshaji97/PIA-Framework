"""Command-line interface."""

import json
import re
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

from . import storage
from .analysis import analyse
from .discovery import PolicyNotFound, locate_policy, lookup_package
from .fetch import FetchError, PolicyDocument, fetch_policy, load_policy_file, looks_like_policy
from .providers import PROVIDERS, LLMError, detect_provider, get_provider
from .report import GRADE_COLOURS, render

BANNER = r"""
  _____      _                         _____                            _
 |  __ \    (_)                       |_   _|                          | |
 | |__) | __ ___   ____ _  ___ _   _    | |  _ __ ___  _ __   __ _  ___| |_
 |  ___/ '__| \ \ / / _` |/ __| | | |   | | | '_ ` _ \| '_ \ / _` |/ __| __|
 | |   | |  | |\ V / (_| | (__| |_| |  _| |_| | | | | | |_) | (_| | (__| |_
 |_|   |_|  |_| \_/ \__,_|\___|\__, | |_____|_| |_| |_| .__/ \__,_|\___|\__|
                                __/ |                 | |
                               |___/                  |_|
     /\
    /  \   ___ ___  ___  ___ ___ _ __ ___   ___ _ __ | |_
   / /\ \ / __/ __|/ _ \/ __/ __| '_ ` _ \ / _ \ '_ \| __|
  / ____ \\__ \__ \  __/\__ \__ \ | | | | |  __/ | | | |_
 /_/    \_\___/___/\___||___/___/_| |_| |_|\___|_| |_|\__|

 Privacy Impact Assessment of third-party dependencies
"""


def load_env_files() -> None:
    """Load API keys and PIA_* settings from ./.env, then ~/.pia/.env. Real environment variables win."""
    for path in (Path.cwd() / ".env", Path.home() / ".pia" / ".env"):
        if path.is_file():
            load_dotenv(path, override=False)


def is_interactive() -> bool:
    return sys.stdin.isatty()


def log(message: str) -> None:
    click.echo(click.style(message, dim=True), err=True)


def ask_for_policy(max_chars: int) -> PolicyDocument:
    """Prompt until the user supplies a usable policy URL or file, or aborts with a blank line."""
    click.echo("Enter the privacy policy URL or a local file path (blank to abort).", err=True)
    while True:
        source = click.prompt("Policy URL or file", default="", show_default=False, err=True).strip()
        if not source:
            raise click.Abort()
        try:
            if Path(source).expanduser().is_file():
                doc = load_policy_file(str(Path(source).expanduser()), max_chars)
            else:
                doc = fetch_policy(source if "://" in source else f"https://{source}", max_chars)
        except (FetchError, OSError) as e:
            log(str(e))
            continue
        if looks_like_policy(doc.text) or click.confirm(
            "That does not look like a privacy policy. Use it anyway?", default=False, err=True
        ):
            return doc


def split_spec(name: str, version: str | None) -> tuple[str, str]:
    """Accept 'NAME VERSION', 'NAME==VERSION' or 'NAME@VERSION' (npm scopes allowed)."""
    if version:
        return name, version
    match = re.fullmatch(r"(@?[^@=\s]+)(?:==|@)(\S+)", name)
    if match:
        return match.group(1), match.group(2)
    raise click.UsageError("Give a version: pia assess NAME VERSION (or NAME==VERSION / NAME@VERSION)")


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Privacy Impact Assessment for third-party dependencies.

    Finds a dependency's privacy policy, has an LLM classify its data collection
    and processing practices, and scores it out of 10 (10 = most protective).
    """
    load_env_files()
    if ctx.invoked_subcommand is None:
        click.echo(BANNER)
        click.echo(ctx.get_help())


@cli.command()
@click.argument("name")
@click.argument("version", required=False)
@click.option("--provider", type=click.Choice(list(PROVIDERS)), envvar="PIA_PROVIDER",
              help="LLM provider. Defaults to whichever API key is set.")
@click.option("--model", envvar="PIA_MODEL", help="Model name. Defaults to the provider's default.")
@click.option("--base-url", envvar="PIA_BASE_URL", help="Custom API endpoint (OpenAI-compatible servers, proxies).")
@click.option("--ecosystem", type=click.Choice(["auto", "pypi", "npm", "none"]), default="auto", show_default=True,
              help="Package registry used to find the vendor's homepage.")
@click.option("--policy-url", help="Analyse this policy URL instead of searching the web for one.")
@click.option("--policy-file", type=click.Path(exists=True, dir_okay=False), help="Analyse a local policy file.")
@click.option("--max-chars", default=100_000, show_default=True, help="Truncate policy text sent to the LLM.")
@click.option("--json", "as_json", is_flag=True, help="Print the assessment as JSON.")
@click.option("--no-save", is_flag=True, help="Do not store the assessment in the history database.")
@click.option("--fail-under", type=float, help="Exit with status 1 if the score is below this value (for CI).")
def assess(name, version, provider, model, base_url, ecosystem, policy_url, policy_file, max_chars,
           as_json, no_save, fail_under):
    """Assess a dependency by name and version (pia assess sentry-sdk 2.19.0)."""
    name, version = split_spec(name, version)

    provider = provider or detect_provider()
    if not provider:
        raise click.UsageError(
            "No LLM provider configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY or GEMINI_API_KEY, "
            "or pass --provider (e.g. --provider ollama for a local model)."
        )
    try:
        llm = get_provider(provider, model, base_url)
    except LLMError as e:
        raise click.ClickException(str(e)) from e

    warnings = []
    pkg = None
    if ecosystem != "none":
        log("Looking up package registry...")
        pkg = lookup_package(name, version, ecosystem)
        if pkg:
            log(f"Found {pkg.name} on {pkg.ecosystem}")
            if not pkg.version_found:
                warnings.append(f"Version {version} of {pkg.name} was not found on {pkg.ecosystem}")
        else:
            log("Not found on PyPI/npm; relying on web search")

    try:
        if policy_file:
            doc = load_policy_file(policy_file, max_chars)
        elif policy_url:
            doc = fetch_policy(policy_url, max_chars)
        else:
            doc = locate_policy(name, pkg, max_chars, log)
    except (PolicyNotFound, FetchError) as e:
        if not is_interactive():
            raise click.ClickException(
                f"{e}\nSpecify the policy manually: pia assess {name} {version} --policy-url URL"
                " (or --policy-file PATH)"
            ) from e
        log(str(e))
        doc = ask_for_policy(max_chars)

    if not looks_like_policy(doc.text):
        warnings.append("The supplied document does not look like a privacy policy")

    log(f"Policy: {doc.source} ({len(doc.text):,} characters)")
    log(f"Analysing with {llm.name} / {llm.model}...")
    try:
        assessment = analyse(name, version, doc, llm)
    except LLMError as e:
        raise click.ClickException(str(e)) from e
    assessment.warnings = warnings + assessment.warnings

    if not no_save:
        assessment_id = storage.save(assessment)
        log(f"Saved as assessment #{assessment_id} in {storage.db_path()}")

    click.echo(json.dumps(assessment.to_dict(), indent=2) if as_json else render(assessment))

    if fail_under is not None and assessment.score < fail_under:
        sys.exit(1)


@cli.command()
@click.option("--limit", default=50, show_default=True)
def history(limit):
    """List past assessments."""
    rows = storage.history(limit)
    if not rows:
        click.echo("No assessments yet. Run `pia assess NAME VERSION`.")
        return
    click.echo(f"{'ID':>4}  {'Dependency':<28} {'Version':<12} {'Score':>6}  {'Grade':<9} {'Model':<24} Date")
    for aid, dep, ver, score, grade, provider, model, created in rows:
        grade_text = click.style(f"{grade:<9}", fg=GRADE_COLOURS.get(grade))
        click.echo(f"{aid:>4}  {dep[:28]:<28} {ver[:12]:<12} {score:>6g}  {grade_text} {model[:24]:<24} {created[:10]}")


@cli.command()
@click.argument("assessment_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Print the assessment as JSON.")
def show(assessment_id, as_json):
    """Show a stored assessment in full."""
    assessment = storage.load(assessment_id)
    if assessment is None:
        raise click.ClickException(f"No assessment with ID {assessment_id}")
    click.echo(json.dumps(assessment.to_dict(), indent=2) if as_json else render(assessment))
