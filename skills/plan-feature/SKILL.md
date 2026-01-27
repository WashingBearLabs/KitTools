---
name: plan-feature
description: Brainstorm and plan a new feature with guided questions
---

# Plan Feature

Let's brainstorm and plan a new feature together. This is an interactive process — I'll ask clarifying questions to help refine the idea before generating the TODO file.

## Step 1: Capture the spark

First, tell me about the feature idea:

- **What's the feature?** (Name and brief description)
- **What problem does it solve?** (The "why")
- **What triggered this idea?** (Were you working on something else? Did you hit a limitation?)

## Step 2: Define the scope

Now let's set clear boundaries. I'll ask about:

### Goal
What's the desired outcome when this feature is complete? Be specific.

### Non-Goals
What is explicitly **not** part of this feature? This prevents scope creep later.

### Success Criteria
How will we know it's done and working correctly? (e.g., "User can log in with OAuth", "API returns results in < 200ms")

## Step 3: Identify dependencies

Before we plan the work:

- Does this feature depend on other features or systems being ready?
- Are there external dependencies (APIs, libraries, services)?
- Any blockers we should note?

## Step 4: Break into phases

Now I'll help structure the implementation into phases. For each phase, we'll define:

1. **Phase name** — What this chunk of work accomplishes
2. **Intent** — Why this phase exists and what completing it enables
3. **Pre-flight questions** — What to confirm/validate before starting this phase
4. **Tasks** — The specific work items

Typical phase structure:
- **Phase 1: Foundation** — Data models, API contracts, scaffolding
- **Phase 2: Core Implementation** — The main functionality
- **Phase 3: Polish & Testing** — Edge cases, error handling, tests, documentation

We can adjust phases based on the feature's complexity.

## Step 5: Surface open questions

What decisions still need to be made? What assumptions are we making that should be validated?

## Step 6: Generate the FEATURE_TODO file

Once we've refined the plan, I'll create `kit_tools/roadmap/FEATURE_TODO_[name].md` with:

- Feature Overview (Status: Planning)
- Feature Scope (Goal, Non-Goals, Success Criteria)
- Origin (Why now, Date captured)
- Phased tasks with intents and pre-flight checks
- Dependencies
- Open Questions
- Empty Notes and Session Tracking sections

## Step 7: Update the backlog

I'll add a reference to the new feature in `kit_tools/roadmap/BACKLOG.md` under "Future Features" so it doesn't get lost.

## Step 8: Summary

I'll provide a summary of:

- The feature we planned
- Where the FEATURE_TODO file was created
- Key decisions made during brainstorming
- Recommended next steps (or note that this is parked for later)

---

**Note:** This skill does NOT change your Active Feature in the scratchpad. You can brainstorm a new feature while working on something else — the TODO file serves as a placeholder for future work.
