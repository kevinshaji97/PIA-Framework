"""Scoring rubric for privacy impact assessments.

The LLM only classifies what a privacy policy says into one of the fixed ratings
below. The score is computed here, deterministically, so results are reproducible
and auditable regardless of which LLM provider is used.

A score of 10 means the most privacy-protective. Criterion weights sum to 10.
"""

from dataclasses import dataclass

NOT_STATED = "not_stated"


@dataclass(frozen=True)
class Criterion:
    key: str
    title: str
    question: str
    # rating -> (points, description shown to the LLM and in reports)
    options: dict[str, tuple[float, str]]

    @property
    def weight(self) -> float:
        return max(points for points, _ in self.options.values())


CRITERIA: tuple[Criterion, ...] = (
    Criterion(
        "data_minimisation",
        "Data collection scope",
        "How much personal data does the service collect or process?",
        {
            "none": (2.0, "No personal data is collected or processed"),
            "minimal": (1.5, "Only data strictly necessary to provide the service"),
            "moderate": (0.75, "Identifiers, device or usage data beyond what is strictly necessary"),
            "extensive": (0.0, "Broad collection, e.g. cross-site/app tracking, inferred data, or data bought from other sources"),
            NOT_STATED: (0.0, "The policy does not say what is collected"),
        },
    ),
    Criterion(
        "sensitive_data",
        "Sensitive data",
        "Does it process sensitive data (health, biometrics, precise location, financial, government IDs, children's data, etc.)?",
        {
            "none": (1.5, "No sensitive data is processed"),
            "explicit_consent_only": (0.75, "Sensitive data only with explicit opt-in consent"),
            "collected": (0.0, "Sensitive data is processed without explicit opt-in consent"),
            NOT_STATED: (0.0, "The policy does not address sensitive data"),
        },
    ),
    Criterion(
        "purpose_limitation",
        "Purpose of processing",
        "What is the personal data used for?",
        {
            "service_only": (1.5, "Only to provide, secure and support the service"),
            "service_and_analytics": (1.0, "Also product analytics or improvement, but not advertising or profiling"),
            "advertising_or_profiling": (0.0, "Advertising, marketing profiles, or training AI models on user data by default"),
            NOT_STATED: (0.0, "Purposes are not stated"),
        },
    ),
    Criterion(
        "third_party_sharing",
        "Third-party sharing",
        "Who is personal data shared with?",
        {
            "none": (1.5, "Not shared with any third party"),
            "processors_only": (1.0, "Only with contracted service providers/processors, or where legally required"),
            "broad": (0.25, "With affiliates, partners or advertisers for their own purposes"),
            "sold": (0.0, "Sold, or shared for cross-context behavioural advertising"),
            NOT_STATED: (0.0, "Sharing is not described"),
        },
    ),
    Criterion(
        "retention",
        "Data retention",
        "How long is personal data kept?",
        {
            "defined": (1.0, "Specific retention periods or deletion schedules"),
            "vague": (0.5, "'As long as necessary' or similar, without concrete periods"),
            "indefinite": (0.0, "Kept indefinitely"),
            NOT_STATED: (0.0, "Retention is not described"),
        },
    ),
    Criterion(
        "user_rights",
        "User rights",
        "Can users access, correct, delete and export their data?",
        {
            "comprehensive": (1.0, "Access, correction, deletion and portability, with a clear way to exercise them"),
            "partial": (0.5, "Some rights, or no clear way to exercise them"),
            "none": (0.0, "No user rights are offered"),
            NOT_STATED: (0.0, "User rights are not described"),
        },
    ),
    Criterion(
        "consent_and_control",
        "Consent and control",
        "How is consent obtained for non-essential processing (analytics, marketing, cookies)?",
        {
            "opt_in": (0.5, "Opt-in, with granular controls"),
            "opt_out": (0.25, "Enabled by default, users can opt out"),
            "none": (0.0, "No way to decline non-essential processing"),
            NOT_STATED: (0.0, "Consent is not described"),
        },
    ),
    Criterion(
        "security",
        "Security measures",
        "How is personal data protected?",
        {
            "specific": (0.5, "Concrete measures, e.g. encryption in transit and at rest, access controls, certifications"),
            "generic": (0.25, "A generic 'reasonable measures' statement"),
            NOT_STATED: (0.0, "Security is not described"),
        },
    ),
    Criterion(
        "international_transfers",
        "International transfers",
        "Is personal data transferred across borders, and with what safeguards?",
        {
            "none_or_safeguarded": (0.5, "Stays in region, or transfers use safeguards (SCCs, adequacy decisions, DPF)"),
            "unsafeguarded": (0.0, "Transferred without stated safeguards"),
            NOT_STATED: (0.0, "Transfers are not described"),
        },
    ),
)

CRITERIA_BY_KEY = {c.key: c for c in CRITERIA}
MAX_SCORE = sum(c.weight for c in CRITERIA)
assert MAX_SCORE == 10, MAX_SCORE

# If nothing personal is collected, every other criterion is moot and gets full marks.
NO_DATA_KEY, NO_DATA_RATING = "data_minimisation", "none"


def score(ratings: dict[str, str]) -> tuple[float, dict[str, float]]:
    """Return (total score out of 10, points per criterion) for validated ratings."""
    no_personal_data = ratings.get(NO_DATA_KEY) == NO_DATA_RATING
    points = {}
    for c in CRITERIA:
        if no_personal_data:
            points[c.key] = c.weight
        else:
            points[c.key] = c.options[ratings.get(c.key, NOT_STATED)][0]
    return round(sum(points.values()), 2), points


def grade(total: float) -> str:
    if total >= 8:
        return "Strong"
    if total >= 6:
        return "Adequate"
    if total >= 4:
        return "Weak"
    return "Poor"
