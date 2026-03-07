"""Console entry point for the investment idea generation app."""

import argparse
import sys


def main() -> None:
    """Run the investment idea generation workflow."""
    parser = argparse.ArgumentParser(description="Investment Idea Generator")
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
    args = parser.parse_args()

    try:
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
        theme = args.theme
        if theme is None:
            theme_input = input(
                "Enter investment theme (default: AI in healthcare): "
            ).strip()
            theme = theme_input if theme_input else "AI in healthcare"

        archetype = args.archetype
        if archetype is None:
            archetype_input = input(
                "Analyst style (Logical/Spock, Visionary, Conservative, Sherlock, "
                "Root-Seeker, or Enter for default): "
            ).strip()
            archetype = archetype_input if archetype_input else None

        print("\nGenerating ideas...")
        brainstorm = brainstorm_ideas(theme, archetype=archetype)
        print("Critiquing ideas...")
        critic = critique_ideas(brainstorm, archetype=archetype)

        summary = format_exec_summary(brainstorm, critic)
        print("\n--- Executive Summary ---\n")
        print(summary)

        trackables = parse_trackable_elements(summary)
        print("\n--- Trackable Elements ---\n")
        for elem in trackables:
            print(f"  Idea {elem['idea_id']}: catalyst={elem.get('catalyst')}, "
                  f"timeline={elem.get('timeline')}, metric={elem.get('metric')}, "
                  f"ticker={elem.get('ticker')}")

        arguments_list = extract_arguments_from_summary(summary)
        if not arguments_list:
            print("\nNo arguments extracted for conviction scoring.")
            return

        print(f"\nEnter weights (1-10) for each of {len(arguments_list)} idea(s), "
              "comma-separated: ")
        weights_input = input().strip()
        if not weights_input:
            weights_list = [5] * len(arguments_list)
            print(f"Using default weight 5 for all {len(arguments_list)} ideas.")
        else:
            try:
                weights_list = [int(w.strip()) for w in weights_input.split(",")]
            except ValueError:
                print("Invalid weights. Use comma-separated integers (e.g., 7,8,6,9).")
                sys.exit(1)

        score = calculate_conviction(arguments_list, weights_list)
        print(f"\n--- Conviction Score: {score}/10 ---")
    except (ValueError, RuntimeError, Exception) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
