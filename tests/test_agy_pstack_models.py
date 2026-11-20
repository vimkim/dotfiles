import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULE_FILE = ROOT / "dot_gemini/config/rules/pstack-models.md"

EXPECTED_ROLES = {
    "feature, refactoring": "inherit-parent",
    "bug-fix": "inherit-parent",
    "perf-issue": "inherit-parent",
    "hillclimb": "inherit-parent",
    "judgment and prose": "inherit-parent",
    "arena runners": "gemini-4-neon-high, claude-opus-5-5-high",
    "arena cross-judge pool": "claude-opus-5-5-high, gemini-4-neon-high",
    "swarm workers": "gemini-4-hydrogen-high",
    "interrogate reviewers": "gemini-4-neon-high, claude-opus-5-5-high",
}

ALLOWED_SLUGS = {
    "inherit-parent",
    "gemini-4-neon-high",
    "gemini-4-hydrogen-high",
    "claude-opus-5-5-high",
}


def parse_rule_file(text: str) -> tuple[dict[str, str], list[str], dict[str, str]]:
    """Split frontmatter, body lines, and parsed role-to-model entries."""
    lines = text.splitlines()
    if len(lines) < 3 or lines[0] != "---":
        raise AssertionError("Rule file must start with YAML frontmatter delimiter '---'")
    try:
        end_idx = lines.index("---", 1)
    except ValueError as exc:
        raise AssertionError("Rule file frontmatter closing delimiter '---' not found") from exc

    frontmatter: dict[str, str] = {}
    for line in lines[1:end_idx]:
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise AssertionError(f"Invalid frontmatter line: {line!r}")
        frontmatter[key.strip()] = value.strip()

    body_lines = lines[end_idx + 1 :]
    roles: dict[str, str] = {}
    for line in body_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        role, sep, value = stripped.partition(":")
        if not sep:
            raise AssertionError(f"Invalid role line: {line!r}")
        roles[role.strip()] = value.strip()

    return frontmatter, body_lines, roles


class AgyPstackModelsTest(unittest.TestCase):
    def test_frontmatter_and_headers(self):
        text = RULE_FILE.read_text(encoding="utf-8")
        frontmatter, body_lines, _ = parse_rule_file(text)
        self.assertEqual(frontmatter.get("trigger"), "always_on")
        self.assertTrue(frontmatter.get("description"))
        self.assertIn("# defaults: 3", body_lines)
        self.assertIn("# budget: medium (high)", body_lines)

    def test_hybrid_roles_and_valid_antigravity_slugs(self):
        text = RULE_FILE.read_text(encoding="utf-8")
        _, _, roles = parse_rule_file(text)
        self.assertEqual(roles, EXPECTED_ROLES)

        for role, raw_value in roles.items():
            tokens = [item.strip() for item in raw_value.split(",")]
            self.assertTrue(all(tokens), f"Empty model entry in role {role!r}")
            for token in tokens:
                self.assertIn(token, ALLOWED_SLUGS, f"Unexpected slug {token!r} in role {role!r}")
                self.assertNotIn("gpt-6.", token)
                self.assertNotIn("-fast", token)
                self.assertNotIn("claude-fable-", token)


if __name__ == "__main__":
    unittest.main()
