---
name: deliverables
description: "Getting a file out of the sandbox and to the user — reports, HTML pages, images, archives, datasets. Use whenever you have produced a file the user should be able to open, download, or keep, or when you are about to hand over a link. Also trigger on 'send me the file', 'give me a download link', 'export this', 'save this as', 'make me a report/page/spreadsheet', or when an export fails and you are deciding what to do next."
display_name: Deliverables
version: "1.0.0"
author: Astralform
---

# Deliverables

How to write a file so it reaches the user, and what to say about the link you hand them.

Getting this wrong is quiet: a file that looks written is unreadable, an export appears to
succeed and delivers nothing, or the user gets a link that dies. Everything below is drawn
from runs where exactly that happened.

## The one rule

**Write deliverables with `capsule.fs.write_file`. Never shell redirection, never Python
`open()`.**

```python
import capsule
capsule.fs.write_file("/workspace/outputs/report.html", html)   # correct
```

```python
# WRONG — the file will look fine and be undeliverable
with open("/workspace/outputs/report.html", "w") as f:
    f.write(html)
```

```bash
# WRONG — same problem
echo "$html" > /workspace/outputs/report.html
```

### Why

`/workspace` is a network mount. A file written straight onto it can be **complete to `cat`
and unreadable through the platform**, at the same time:

| How you read it | What you get |
|---|---|
| `wc -c` / `md5sum` in the shell | 49,175 bytes, stable checksum |
| `capsule.fs.read_file` | **4 bytes** |

`export_file` uses the platform path. So the file exists, looks perfect in the shell, and
cannot be exported — and the error says it is "still saving", which never becomes true.

**Recognise it by that signature**: shell says the file is fine, the platform says it is
empty or tiny. If you see that, rewrite the file with `capsule.fs.write_file` and export
again. Do not retry the export unchanged.

## Where to write

`/workspace/outputs/` — that is what `export_file` reads by default and what the user's
files list shows.

## Getting it to the user

```
export_file(path="/workspace/outputs/report.html", name="Q3 Report.html")
```

Returns a **permanent address**. It stays valid, the file appears in the conversation's
files list, and it survives a page refresh. Hand that link over as-is.

Two things to be accurate about when you describe it:

- It is a link **the user** opens — it is authenticated as them, not a public URL. Do not
  describe it as something they can forward to anyone, publish, or embed on a website.
- **We do not host websites.** If the user asks for their page to be "live" or "hosted",
  say plainly that you can give them the file and a link to it, not a public site.

### Which tool

| Tool | Use it for |
|---|---|
| `export_file` | **Deliverables.** Records the file so it appears in the files list |
| `capsule_download_url` | A link to a file you do not want listed as a deliverable |
| `capsule_get_url` | **Never for the user.** Points at the sandbox VM and dies with it |

`capsule_get_url` is a live preview for checking your own work. Handing it over produces a
link that 502s as soon as the sandbox is reclaimed — usually minutes later, long after you
have moved on.

## When an export fails

Read which failure it is; they need different responses.

**"hasn't finished saving to storage yet"** — a large upload may genuinely still be landing.
Wait a few seconds and call `export_file` once more. If it repeats, treat it as the
mount-incoherency signature above: rewrite with `capsule.fs.write_file`, then export.

**"could not be saved to storage. STOP calling export_file"** — terminal for that file. It
means what it says: do not retry, and do not substitute a `capsule_get_url` link. Tell the
user plainly that the file could not be delivered, and if it is small, put the content
directly in your reply.

**"no file at &lt;path&gt;"** — you have not written it yet, or wrote it somewhere else.
Check the path.

## Common mistakes

- **Handing over `capsule_get_url`** because `export_file` failed. That is the same failure
  with a delay on it.
- **Retrying an unchanged export** after the terminal message. The budget is spent; the
  answer will not change.
- **Reporting success you have not confirmed.** Only call it delivered once `export_file`
  returns a link.
- **Promising hosting.** A file and a link is what exists.
- **Writing to `/tmp` and forgetting to move it.** `/tmp` is sandbox-local and vanishes;
  only `/workspace` persists.
