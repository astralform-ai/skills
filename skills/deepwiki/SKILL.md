---
name: deepwiki
description: Look up AI-generated documentation for any public GitHub repository using DeepWiki. Use when the user asks about a GitHub repo's architecture, how it works, its API, or needs to understand unfamiliar code.
display_name: DeepWiki
version: "1.0.0"
author: Astralform
---

# DeepWiki

Query AI-generated wiki documentation for any public GitHub repository via the DeepWiki MCP service by Cognition AI.

## When to Use

- User asks "how does {repo} work?" or "explain {repo}'s architecture"
- Need to understand an unfamiliar GitHub repo before integrating with it
- Researching a library's internals, API design, or structure
- Comparing how different repos solve similar problems

## MCP Service

DeepWiki is a free, hosted MCP service — no API key required.

**Endpoint:** `https://mcp.deepwiki.com/mcp` (Streamable HTTP)

### Available Tools

| Tool | Description |
|---|---|
| `read_wiki_structure` | Get the list of documentation topics for a repo |
| `read_wiki_contents` | Read documentation about a specific topic in a repo |
| `ask_question` | Ask any question about a repo and get an AI-grounded answer |

## Workflow

### 1. Explore repo structure first

Call `read_wiki_structure` with the repo (e.g., `langchain-ai/langchain`) to see what topics are documented.

### 2. Read relevant sections

Call `read_wiki_contents` for the specific topics that match what the user is asking about.

### 3. Ask targeted questions

Use `ask_question` for specific queries like "How does the routing layer work?" or "What database does this project use?"

## Usage Tips

- Works with **public repositories only**
- Start broad (structure) then drill into specific topics
- The `ask_question` tool is best for specific technical questions
- Combine with web search for the most comprehensive research
- Great for understanding dependencies before adding them to a project

## Example Queries

| User Request | Approach |
|---|---|
| "How does LangGraph work?" | `read_wiki_structure` → `read_wiki_contents` on key topics |
| "What's the architecture of Astralform?" | `read_wiki_structure` → read architecture + API sections |
| "Does this repo support streaming?" | `ask_question`: "Does this project support streaming responses?" |
| "Compare how X and Y handle auth" | Query both repos' auth sections, then synthesize |
