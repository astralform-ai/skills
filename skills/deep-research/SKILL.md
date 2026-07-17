---
name: deep-research
description: Systematic multi-angle web research methodology. Use instead of a single search for ANY question requiring web research — "what is X", "explain X", "compare X and Y", "research X", or before content generation tasks. Provides comprehensive multi-source research rather than superficial single searches.
display_name: Deep Research
version: "1.0.1"
author: Astralform
---

# Deep Research

## Overview

This skill provides a systematic methodology for conducting thorough web research. **Load this skill BEFORE starting any content generation task** to ensure you gather sufficient information from multiple angles, depths, and sources.

## When to Use

**Always use this skill when:**

- User asks "what is X", "explain X", "research X", "investigate X"
- User wants to understand a concept, technology, or topic in depth
- The question requires current, comprehensive information from multiple sources
- A single web search would be insufficient to answer properly
- Creating presentations, articles, reports, designs, or any content requiring real-world information

## Core Principle

**Never generate content based solely on general knowledge.** The quality of your output depends on the quality and quantity of research conducted. A single search query is NEVER enough.

## Research Methodology

### Phase 1: Broad Exploration

Start with broad searches to understand the landscape:

1. **Initial Survey**: Search for the main topic to understand overall context
2. **Identify Dimensions**: From initial results, identify key subtopics, themes, and angles
3. **Map the Territory**: Note different perspectives, stakeholders, or viewpoints

Example:
```
Topic: "AI in healthcare"
Initial searches:
- "AI healthcare applications 2025"
- "artificial intelligence medical diagnosis"
- "healthcare AI market trends"

Identified dimensions:
- Diagnostic AI (radiology, pathology)
- Treatment recommendation systems
- Administrative automation
- Regulatory landscape
- Ethical considerations
```

### Phase 2: Deep Dive

For each important dimension, conduct targeted research:

1. **Specific Queries**: Search with precise keywords for each subtopic
2. **Multiple Phrasings**: Try different keyword combinations
3. **Fetch Full Content**: Use available fetch/extract tools to read important sources in full, not just snippets
4. **Follow References**: When sources mention other important resources, search for those too

### Phase 3: Diversity & Validation

Ensure comprehensive coverage by seeking diverse information types:

| Information Type | Purpose | Example Search Qualifiers |
|---|---|---|
| **Facts & Data** | Concrete evidence | "statistics", "data", "market size" |
| **Examples & Cases** | Real-world applications | "case study", "implementation" |
| **Expert Opinions** | Authority perspectives | "expert analysis", "interview" |
| **Trends** | Future direction | "trends", "forecast", "future of" |
| **Comparisons** | Context and alternatives | "vs", "comparison", "alternatives" |
| **Challenges** | Balanced view | "challenges", "limitations", "criticism" |

### Phase 4: Synthesis Check

Before proceeding to content generation, verify:

- [ ] Searched from at least 3-5 different angles?
- [ ] Fetched and read the most important sources in full?
- [ ] Have concrete data, examples, and expert perspectives?
- [ ] Explored both positive aspects and challenges/limitations?
- [ ] Information is current and from authoritative sources?

**If any answer is NO, continue researching before generating content.**

## Search Strategy

### Effective Query Patterns

```
# Be specific with context
BAD:  "AI trends"
GOOD: "enterprise AI adoption trends 2025"

# Include authoritative source hints
"[topic] research paper"
"[topic] McKinsey report"
"[topic] industry analysis"

# Search for specific content types
"[topic] case study"
"[topic] statistics"
"[topic] expert interview"

# Use temporal qualifiers with the ACTUAL current date
"[topic] March 2026"
"[topic] latest"
"[topic] recent developments"
```

### Temporal Awareness

**Always check the current date before forming search queries.**

| User Intent | Precision Needed | Example Query |
|---|---|---|
| "today / just released" | Month + Day + Year | `"tech news March 20 2026"` |
| "this week" | Week range | `"releases week of March 17 2026"` |
| "recently / latest" | Month + Year | `"AI breakthroughs March 2026"` |
| "this year / trends" | Year | `"software trends 2026"` |

**Rules:**
- When user asks about "today", use month + day + year — year-only queries miss current results
- Try multiple phrasings: numeric, written, and relative terms across queries

### When to Fetch Full Content

Use available fetch/extract tools to read full content when:
- A search result looks highly relevant and authoritative
- You need detailed information beyond the snippet
- The source contains data, case studies, or expert analysis
- You want to understand the full context of a finding

### Iterative Refinement

Research is iterative:
1. Review what you've learned
2. Identify gaps in understanding
3. Formulate new, targeted queries
4. Repeat until comprehensive coverage

## Quality Bar

Research is sufficient when you can confidently answer:
- What are the key facts and data points?
- What are 2-3 concrete real-world examples?
- What do experts say about this topic?
- What are the current trends and future directions?
- What are the challenges or limitations?
- What makes this topic relevant or important now?

## Common Mistakes

- Stopping after 1-2 searches
- Relying on search snippets without reading full sources
- Searching only one aspect of a multi-faceted topic
- Ignoring contradicting viewpoints or challenges
- Using outdated information when current data exists
- Starting content generation before research is complete
