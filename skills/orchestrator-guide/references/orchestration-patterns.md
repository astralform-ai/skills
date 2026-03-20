# Orchestration Patterns

## Fan-Out / Fan-In

Distribute independent sub-tasks to multiple agents in parallel, then combine results.

**Use when:** The user's request has multiple independent parts.

**Example flow:**
- User: "Compare pricing, features, and reviews for these 3 products"
- Fan-out: Agent A → pricing, Agent B → features, Agent C → reviews
- Fan-in: Combine into a comparison table

## Pipeline

Chain agents sequentially where each stage's output feeds the next.

**Use when:** Tasks have clear dependencies.

**Example flow:**
- User: "Research this topic and write a blog post about it"
- Stage 1: Research agent gathers information
- Stage 2: Writing agent drafts the post using research output
- Stage 3: Review agent polishes the draft

## Router

Analyze the request and route to a single specialist agent.

**Use when:** The request clearly belongs to one domain.

**Example flow:**
- User: "Fix this CSS layout bug"
- Route to: Frontend agent with CSS/design skills

## Iterative Refinement

Run a task, evaluate the output, and re-run with feedback.

**Use when:** Quality matters and the first attempt may need improvement.

**Example flow:**
- Agent produces draft → Evaluator agent scores it → Original agent revises based on feedback
- Repeat until quality threshold is met or max iterations reached

## Supervisor

Maintain oversight of long-running multi-agent tasks.

**Use when:** The workflow is complex and may need dynamic re-planning.

**Responsibilities:**
- Track which sub-tasks are complete
- Re-prioritize if new information emerges
- Aggregate partial results for progress updates
- Decide when to stop iterating
