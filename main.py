"""Console entry point for the investment idea generation app."""

import argparse
import sys


def _prompt_theme() -> str:
    text = input("\nInvestment theme (default: AI in healthcare): ").strip()
    return text or "AI in healthcare"


def _prompt_archetype() -> str | None:
    from src.config import ANALYST_ARCHETYPES

    print("\nAnalyst style:")
    print("  0. Default (no preference)")
    keys = list(ANALYST_ARCHETYPES.keys())
    for i, key in enumerate(keys, start=1):
        data = ANALYST_ARCHETYPES[key]
        aliases = ", ".join(data["aliases"])
        print(f"  {i}. {data['display_name']} ({aliases})")
    upper = len(keys)
    raw = input(
        f"\nSelect number [0–{upper}, default 0]: "
    ).strip() or "0"
    try:
        n = int(raw)
    except ValueError:
        print("Invalid input — using default (no preference).")
        return None
    if n == 0:
        return None
    if 1 <= n <= upper:
        return ANALYST_ARCHETYPES[keys[n - 1]]["display_name"]
    print("Out of range — using default (no preference).")
    return None


def _prompt_use_web_rag() -> bool:
    print()
    hint = input(
        "Use Exa web context (RAG) before brainstorming? [Y/n]: "
    ).strip().lower()
    return hint not in ("n", "no")


def _maybe_export_notion_cli(
    summary: str,
    trackables: list,
    theme: str,
) -> None:
    """If user confirms, export summary+trackables to Notion (same as Streamlit)."""
    ans = input("\nExport results to Notion? [y/N]: ").strip().lower()
    if ans not in ("y", "yes"):
        return
    from src.idea_exporter import export_to_notion

    print("• Exporting to Notion (includes keyword generation)...", flush=True)
    try:
        msg = export_to_notion(summary, trackables, theme)
        print(msg)
    except (ValueError, RuntimeError) as e:
        print(f"Notion export failed: {e}", file=sys.stderr)


def main() -> None:
    """Run the investment idea generation workflow."""
    parser = argparse.ArgumentParser(
        description="Investment Idea Generator",
        epilog=(
            "When both --theme and --archetype are set, web RAG defaults to on "
            "unless --no-web-context is passed (non-interactive). Otherwise you "
            "will be asked about RAG interactively."
        ),
    )
    parser.add_argument(
        "--archetype",
        "-a",
        type=str,
        default=None,
        help="Analyst style: Logical/Spock, Visionary, Conservative, Sherlock, Root-Seeker",
    )
    parser.add_argument(
        "--theme",
        "-t",
        type=str,
        default=None,
        help="Investment theme (default: AI in healthcare)",
    )
    parser.add_argument(
        "--no-web-context",
        action="store_true",
        help="Skip Exa web retrieval for the Brainstormer (no extra API call)",
    )
    args = parser.parse_args()

    try:
        from src.config import EXA_API_KEY
        from src.context_retrieval import fetch_web_context_markdown
        from src.llm_analysts import brainstorm_ideas, critique_ideas
        from src.summary_generator import (
            calculate_conviction,
            extract_arguments_from_summary,
            format_exec_summary,
            parse_trackable_elements,
        )
    except (ValueError, ImportError) as e:
        print(f"Setup error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        theme = args.theme if args.theme is not None else _prompt_theme()

        archetype = (
            args.archetype if args.archetype is not None else _prompt_archetype()
        )

        if args.no_web_context:
            use_web_context = False
        elif args.theme is not None and args.archetype is not None:
            use_web_context = True
        else:
            use_web_context = _prompt_use_web_rag()

        prefetch: str | None = None
        if use_web_context:
            if EXA_API_KEY:
                print("• Fetching recent web snippets (Exa)...", flush=True)
                prefetch = fetch_web_context_markdown(theme)
                if prefetch:
                    print("  Retrieved context for the brainstormer.", flush=True)
                else:
                    print(
                        "  No snippets returned (empty or API issue). Continuing.",
                        flush=True,
                    )
            else:
                print(
                    "• Web RAG requested but EXA_API_KEY is not set; "
                    "continuing without snippets.",
                    flush=True,
                )
                prefetch = ""

        print("• Brainstorming with Grok...", flush=True)
        brainstorm = brainstorm_ideas(
            theme,
            archetype=archetype,
            use_web_context=use_web_context,
            retrieval_context=prefetch if use_web_context else None,
        )
        print("• Critiquing with Grok...", flush=True)
        critic = critique_ideas(brainstorm, archetype=archetype)

        summary = format_exec_summary(brainstorm, critic)
        print("\n--- Executive Summary ---\n")
        print(summary)

        trackables = parse_trackable_elements(summary)
        print("\n--- Trackable Elements ---\n")
        for elem in trackables:
            print(
                f"  Idea {elem['idea_id']}: catalyst={elem.get('catalyst')}, "
                f"timeline={elem.get('timeline')}, metric={elem.get('metric')}, "
                f"ticker={elem.get('ticker')}"
            )

        arguments_list = extract_arguments_from_summary(summary)
        if not arguments_list:
            print("\nNo arguments extracted for conviction scoring.")
            _maybe_export_notion_cli(summary, trackables, theme)
            return

        print(
            f"\nEnter weights (1-10) for each of {len(arguments_list)} idea(s), "
            "comma-separated: "
        )
        weights_input = input().strip()
        if not weights_input:
            weights_list = [5] * len(arguments_list)
            print(f"Using default weight 5 for all {len(arguments_list)} ideas.")
        else:
            try:
                weights_list = [int(w.strip()) for w in weights_input.split(",")]
            except ValueError:
                print(
                    "Invalid weights. Use comma-separated integers (e.g., 7,8,6,9)."
                )
                sys.exit(1)

        score = calculate_conviction(arguments_list, weights_list)
        print(f"\n--- Conviction Score: {score}/10 ---")
        _maybe_export_notion_cli(summary, trackables, theme)
    except (ValueError, RuntimeError, Exception) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
