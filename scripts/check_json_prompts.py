from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from client import check_system_prompt_contains_full_profile


def main() -> int:
    check_system_prompt_contains_full_profile(
        "meta-nihilizm-epistemiczny",
        profile_kind="agent",
        required_top_level_keys=(
            "profile_version",
            "profile_type",
            "agent_identity",
            "epistemology",
            "expression_policy",
        ),
    )

    check_system_prompt_contains_full_profile(
        "_analyser",
        profile_kind="tool",
        required_top_level_keys=(
            "profile_version",
            "profile_type",
            "agent_identity",
            "output_contract",
            "cognitive_dynamics",
        ),
    )

    print("JSON prompt checks passed for agent 'meta-nihilizm-epistemiczny' and tool '_analyser'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())