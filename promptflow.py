#!/usr/bin/env python3
"""
PromptFlow — a zero-dependency prompt-chain runner & library.
Sells as: "prompt chains / multi-step AI workflows" (market: €105–€420 on PeoplePerHour)

Two parts:

1. A LIBRARY of ready-to-use, professionally engineered prompt chains
   (YAML), covering the most-bought workflow categories:
     - research_synthesis   (€345-market: research & synthesis chains)
     - content_pipeline     (€420-market: draft-to-publication pipeline)
     - spec_to_code         (€540-market: specification to tested code)
     - self_refining        (€210-market: iterative self-refining loops)

2. A RUNNER (this file) that executes a chain step-by-step: feed it each
   step's prompt with variables substituted, take your (human or AI) answer,
   carry the output forward as input to the next step.

Why human/AI-agnostic: the runner never calls an API — you paste prompts
into any model you like (ChatGPT, Claude, GLM, local models). This makes it
a template + methodology product with zero maintenance and no API keys,
which is exactly what sells: the buyer gets the engineering, not a liability.

Usage:
    python promptflow.py list                      # show available chains
    python promptflow.py show <chain>              # print a chain's full spec
    python promptflow.py run <chain> [VAR=value].. # run interactively
    python promptflow.py export <chain> --out DIR  # export chain as .md files

Interactive run: each step's prompt is printed (with variables filled),
you paste it into your model of choice, paste the answer back, and the
runner stores outputs and feeds them into later steps.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Chain library. Each chain: name, market, steps[{id, instruction, template}]
# Templates use {variable} placeholders; {{input}} = previous step's output.
# ---------------------------------------------------------------------------

CHAIN_LIB = {
    "research_synthesis": {
        "title": "Research & Synthesis Chain",
        "market": "≈ €345 service equivalent (research & synthesis chains)",
        "purpose": "Turn a raw topic into a cited, structured synthesis report.",
        "steps": [
            {
                "id": "scope",
                "instruction": "Define the research questions precisely before gathering anything.",
                "template": (
                    "You are a senior research analyst. Topic: {topic}.\n"
                    "Produce: (1) the 3-5 specific research questions this topic actually "
                    "requires answering, (2) the 5-8 most credible source types to consult, "
                    "(3) explicit scope boundaries — what is OUT of scope and why. "
                    "Be concise; this scoping steers every later step."
                ),
            },
            {
                "id": "gather",
                "instruction": "Collect raw findings per research question. Paste the scope output first.",
                "template": (
                    "Given this research scope:\n{{input}}\n\n"
                    "For each research question, list concrete findings with source attribution "
                    "(title/publisher/date, or URL if provided). Mark each finding as "
                    "[STRONG], [CONTESTED], or [WEAK] based on source quality. Flag contradictions "
                    "between sources explicitly rather than resolving them silently."
                ),
            },
            {
                "id": "synthesize",
                "instruction": "Resolve contradictions and rank what actually matters.",
                "template": (
                    "Here are gathered findings:\n{{input}}\n\n"
                    "Synthesize: (1) resolve or quantify the contradictions flagged earlier, "
                    "(2) rank the findings by decision-relevance, (3) state the 3 insights that "
                    "would NOT be obvious to someone skimming the sources, (4) list what remains "
                    "genuinely unknown."
                ),
            },
            {
                "id": "report",
                "instruction": "Produce the final deliverable.",
                "template": (
                    "From this synthesis:\n{{input}}\n\n"
                    "Write the final report titled '{topic}'. Structure: executive summary (5 "
                    "sentences max), key findings with evidence tiers, implications, unknowns, "
                    "and a one-paragraph recommendation. Audience: {audience}. Tone: direct, "
                    "no filler, numbers wherever available."
                ),
            },
        ],
    },
    "content_pipeline": {
        "title": "Draft-to-Publication Content Pipeline",
        "market": "≈ €420 service equivalent (content draft-to-publication pipeline)",
        "purpose": "Turn one raw idea into publish-ready content for a chosen channel.",
        "steps": [
            {
                "id": "angle",
                "instruction": "Find the sharpest angle before writing a word.",
                "template": (
                    "Content idea: {idea}. Target channel: {channel}. Audience: {audience}.\n"
                    "Generate 5 distinct angles. For each: the hook (one sentence), why this "
                    "audience cares, and the risk (what makes it flop). Then mark the single "
                    "strongest and justify the choice in 2 sentences."
                ),
            },
            {
                "id": "outline",
                "instruction": "Lock the structure against the chosen angle.",
                "template": (
                    "Chosen angle:\n{{input}}\n\n"
                    "Produce a section-by-section outline for {channel}. For each section: its "
                    "job (hook/proof/story/CTA), 2-3 bullet content notes, and the transition "
                    "into the next. Include a first-sentence draft for the opening section only."
                ),
            },
            {
                "id": "draft",
                "instruction": "Write the full draft following the outline exactly.",
                "template": (
                    "Outline:\n{{input}}\n\n"
                    "Write the complete piece for {channel}, audience {audience}. Rules: match the "
                    "channel's native format and length norms, front-load value, cut every "
                    "sentence that only sounds nice, keep paragraphs scannable. Do not add new "
                    "sections beyond the outline."
                ),
            },
            {
                "id": "polish",
                "instruction": "Edit to publication standard.",
                "template": (
                    "Draft:\n{{input}}\n\n"
                    "Act as a ruthless editor for {channel}. Pass 1: cut weak openers and "
                    "redundancy. Pass 2: strengthen verbs, make claims specific. Pass 3: "
                    "fact-check flags — list every claim that needs verification before "
                    "publishing. Output the final version, then the verification checklist."
                ),
            },
        ],
    },
    "spec_to_code": {
        "title": "Specification-to-Tested-Code",
        "market": "≈ €540 service equivalent (code generation, spec-to-tested-code)",
        "purpose": "Convert a plain-language spec into implemented, tested code.",
        "steps": [
            {
                "id": "clarify",
                "instruction": "Extract every requirement and ambiguity from the spec.",
                "template": (
                    "Specification:\n{spec}\n\n"
                    "List: (1) every functional requirement as a testable statement, "
                    "(2) every ambiguity in the spec with the question that resolves it, "
                    "(3) edge cases the spec forgot, (4) the acceptance checklist the code "
                    "must pass. Number everything."
                ),
            },
            {
                "id": "design",
                "instruction": "Design before coding.",
                "template": (
                    "Requirements and edge cases:\n{{input}}\n\n"
                    "Language: {language}. Design the solution: module/function breakdown, data "
                    "structures with rationale, error-handling strategy, and which requirements "
                    "each function satisfies. Keep it implementation-ready — no hand-waving."
                ),
            },
            {
                "id": "implement",
                "instruction": "Write the complete code from the design.",
                "template": (
                    "Design:\n{{input}}\n\n"
                    "Implement it fully in {language}. Every requirement gets code. Include the "
                    "test cases from the acceptance checklist as runnable tests. No TODOs, no "
                    "placeholder functions — complete or nothing."
                ),
            },
            {
                "id": "verify",
                "instruction": "Adversarial self-review of the implementation.",
                "template": (
                    "Implementation:\n{{input}}\n\n"
                    "Review as a hostile senior engineer: (1) trace each acceptance-checklist "
                    "item through the code — pass/fail with line references, (2) find the 3 "
                    "most likely runtime failures and their triggers, (3) list any missing "
                    "input validation. Output a verdict: SHIP or FIX (with the fix list)."
                ),
            },
        ],
    },
    "self_refining": {
        "title": "Iterative Self-Refining Loop",
        "market": "≈ €210 service equivalent (iterative self-refining loops)",
        "purpose": "Improve any artifact through structured critique/refine rounds.",
        "steps": [
            {
                "id": "baseline",
                "instruction": "Capture the artifact and its success criteria.",
                "template": (
                    "Artifact to improve:\n{artifact}\n\n"
                    "Goal: {goal}. Define the 5 criteria a perfect version of this artifact "
                    "meets, weighted by importance. These criteria are the fixed scoreboard "
                    "for all rounds."
                ),
            },
            {
                "id": "critique",
                "instruction": "Critique honestly against the scoreboard.",
                "template": (
                    "Current artifact:\n{{input}}\n\n"
                    "Score it 1-10 against each criterion from the previous step. For any "
                    "criterion under 8: name the specific deficiency with an example, and state "
                    "exactly what a 10 looks like. No encouragement, no hedging — diagnostics only."
                ),
            },
            {
                "id": "refine",
                "instruction": "Fix the named deficiencies, change nothing else.",
                "template": (
                    "Critique:\n{{input}}\n\n"
                    "Rewrite the artifact fixing ONLY the deficiencies under 8. Keep everything "
                    "that scored well intact. Output the full revised artifact, then a one-line "
                    "note per fix confirming what changed."
                ),
            },
            {
                "id": "recheck",
                "instruction": "Verify the round worked and decide whether to iterate again.",
                "template": (
                    "Revised artifact:\n{{input}}\n\n"
                    "Re-score against the same criteria. If all criteria are 8+, declare DONE "
                    "with a summary of improvements across rounds. If not, list the remaining "
                    "gaps and say ITERATE — the loop returns to critique with the current version."
                ),
            },
        ],
    },
}


VARIABLE_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


def chain_variables(chain):
    """Collect all {variables} across templates, excluding the {{input}} passthrough."""
    variables = set()
    for step in chain["steps"]:
        for match in VARIABLE_RE.findall(step["template"].replace("{{input}}", "")):
            variables.add(match)
    return sorted(variables)


def render(template: str, variables: dict, previous_output: str) -> str:
    """Substitute variables; {{input}} becomes the previous step's output."""
    text = template.replace("{{input}}", previous_output)
    for name, value in variables.items():
        text = text.replace("{" + name + "}", str(value))
    return text


def cmd_list(_args):
    print(f"{len(CHAIN_LIB)} prompt chains available:\n")
    for key, chain in CHAIN_LIB.items():
        needed = ", ".join(chain_variables(chain)) or "none"
        print(f"  {key:22s} {chain['title']}")
        print(f"  {'':22s} {chain['purpose']}")
        print(f"  {'':22s} market value: {chain['market']}")
        print(f"  {'':22s} variables needed: {needed}")
        print(f"  {'':22s} steps: {len(chain['steps'])}\n")


def cmd_show(args):
    chain = CHAIN_LIB[args.chain]
    print(f"# {chain['title']}")
    print(f"# market value: {chain['market']}\n")
    for step in chain["steps"]:
        print(f"## Step {step['id']} — {step['instruction']}\n")
        print(step["template"])
        print("\n" + "-" * 70 + "\n")


def cmd_run(args):
    chain = CHAIN_LIB[args.chain]
    variables = {}
    for pair in args.vars or []:
        name, _, value = pair.partition("=")
        if not value:
            sys.exit(f"error: VAR=value pair '{pair}' has no value")
        variables[name] = value

    missing = [v for v in chain_variables(chain) if v not in variables]
    for name in missing:
        value = input(f"Enter value for '{name}': ").strip()
        if not value:
            sys.exit(f"error: '{name}' is required")
        variables[name] = value

    print(f"\n=== Running chain: {chain['title']} "
          f"({len(chain['steps'])} steps) ===\n")
    previous_output = ""
    outputs = {}
    for i, step in enumerate(chain["steps"], 1):
        print(f"\n--- STEP {i}/{len(chain['steps'])}: {step['id']} ---")
        print(f"purpose: {step['instruction']}\n")
        prompt = render(step["template"], variables, previous_output)
        print("PROMPT (copy into your model):\n")
        print(prompt)
        print("\nPaste the model's answer for this step, end with a blank line:")
        lines = []
        while True:
            line = input()
            if line == "" and lines:
                break
            if line:
                lines.append(line)
        answer = "\n".join(lines).strip()
        if not answer:
            sys.exit("error: empty answer — chain aborted")
        outputs[step["id"]] = answer
        previous_output = answer

    print(f"\n=== Chain complete: {args.chain} ===")
    if args.save:
        Path(args.save).write_text(
            json.dumps({"chain": args.chain, "variables": variables,
                        "outputs": outputs}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"Run saved to {args.save}")


def cmd_export(args):
    out_dir = Path(args.out or f"chain-{args.chain}")
    chain = CHAIN_LIB[args.chain]
    out_dir.mkdir(parents=True, exist_ok=True)
    readme = [
        f"# {chain['title']}",
        "",
        f"**Market value:** {chain['market']}",
        "",
        f"**Purpose:** {chain['purpose']}",
        "",
        f"**How to run:** open each step file in order, paste the prompt into any AI "
        f"model (ChatGPT, Claude, GLM, etc.), then paste the model's answer into the next "
        f"step where you see {{input}}. The runner `promptflow.py` automates this.",
        "",
    ]
    (out_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")
    for step in chain["steps"]:
        content = [
            f"# Step: {step['id']}",
            "",
            f"*{step['instruction']}*",
            "",
            "```",
            step["template"],
            "```",
        ]
        (out_dir / f"{step['id']}.md").write_text("\n".join(content), encoding="utf-8")
    print(f"Exported chain '{args.chain}' ({len(chain['steps'])} steps) to {out_dir}/")


def main():
    parser = argparse.ArgumentParser(prog="promptflow",
                                     description="Prompt-chain runner & library.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list available chains").set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="print a chain's full spec")
    p_show.add_argument("chain", choices=sorted(CHAIN_LIB))
    p_show.set_defaults(func=cmd_show)

    p_run = sub.add_parser("run", help="run a chain interactively")
    p_run.add_argument("chain", choices=sorted(CHAIN_LIB))
    p_run.add_argument("vars", nargs="*", metavar="VAR=value",
                       help="chain variables, e.g. topic='quantum computing'")
    p_run.add_argument("--save", help="save the run (prompts+answers) to a JSON file")
    p_run.set_defaults(func=cmd_run)

    p_exp = sub.add_parser("export", help="export a chain as .md files")
    p_exp.add_argument("chain", choices=sorted(CHAIN_LIB))
    p_exp.add_argument("--out", help="output directory")
    p_exp.set_defaults(func=cmd_export)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
