# Cloud runtime

Everything here runs in the Astralform code capsule via `capsule_run_code`.
The numbers below were measured in that capsule, not assumed — they are the
reason the pipeline is shaped the way it is.

## What the capsule gives you

| | |
|---|---|
| OS | Debian 13 (trixie), user `user`, `sudo` available |
| CPU / RAM | **2 vCPU, ~2 GB** |
| Disk | 4.6 GB total, **~1.4 GB free** before you install anything |
| Present | Python 3.13, **Pillow**, numpy, matplotlib, requests, httpx, Node 20, git, curl, fontconfig |
| Fonts | **Noto Sans CJK (SC/TC/JP) and DejaVu are already installed** — Chinese, Japanese and Korean render out of the box |
| Absent | **ffmpeg**, and **any browser** |
| Egress | pypi, npm and the Debian archives are reachable |

`{baseDir}/scripts/bootstrap.sh` installs ffmpeg (~25 s) and prints this envelope for the
current box. Run it once per session before anything else.

## The five constraints that shape the pipeline

**1. There is no `bash` kernel.**
`capsule_run_code` offers `python` and `javascript` only; asking for `bash`
fails with *"The 'bash' kernel is not available"*. Every shell command therefore
goes through the in-sandbox library from the Python kernel —
`capsule.proc.exec("…")` — which returns `{ok, exit_code, stdout, stderr}` and
**never raises**. An unchecked call looks like success while producing nothing,
so check `ok` every time (that is what the `run` helper in SKILL.md is for). The
kernel is stateful, so the helper survives between calls, and its working
directory is `/home/user` — the same root skill files are written relative to.

**2. A `capsule_run_code` call is killed at 300 seconds.**
The backend does not override the code interpreter's `DEFAULT_TIMEOUT`, so five
minutes is a hard ceiling per call. Encoding is therefore a stage you can run in
ranges — `build_video.py --stage clips --from 1 --to 8`, then `--from 9` — and
each range is resumable because clips are written to `clips/` as they finish.
Budget roughly **0.6 seconds of encoding per second of finished video**, so keep
a single call under about seven minutes of footage.

**3. `zoompan` exhausts the box and the sandbox is killed.**
The classic Ken Burns filter allocates per-frame scaled buffers and, on 2 GB,
takes the whole sandbox down mid-render — verified twice, and it fails by
disappearing rather than erroring. Motion is a **crop window sliding across the
render headroom** instead: `crop=1920:1080:x='(in_w-1920)*min(t/D,1)'`. Same
effect on screen, about 3 seconds per 5-second clip, flat memory.

**4. There is no browser, and adding one does not fit.**
Playwright's `chromium-headless-shell` downloads 266 MB, then fails to start
(`libnspr4.so` missing) and leaves under 300 MB free — before a single frame is
rendered. That is why scenes are composited with **Pillow**, which is already
installed and renders a 1920×1080 scene in well under a second.

**5. Disk is the scarcest resource.**
ffmpeg alone takes free space from ~1.4 GB to ~750 MB. Work at **1080p**; 4K is
not available here in any useful sense. Delete `scenes/` and `clips/` once the
master exists, and keep only what you are delivering.

## Rendering at 1080p, not 4K

The source pipeline this skill is adapted from renders a 4K master by
super-sampling in a browser. That needs a GPU-backed desktop and tens of
gigabytes; here it would exceed both memory and disk. 1080p at CRF 20 is the
master. If a 4K deliverable is genuinely required, render the scene stills at
3840×2160 with `render_scenes.py` (they are just PNGs and Pillow handles it) and
encode on a machine with room — but say so rather than quietly shipping an
upscale.

## Working with the 300-second ceiling

For a long episode, drive it as several calls:

```python
run(f"bash {SK}/scripts/bootstrap.sh")                      # once per session
run(f"python3 {SK}/scripts/render_scenes.py ep/plan.json -o ep/scenes/")
run(f"python3 {SK}/scripts/build_video.py ep/plan.json --work ep/clips "
    f"--scenes ep/scenes --stage clips --from 1 --to 8")
run(f"python3 {SK}/scripts/build_video.py ep/plan.json --work ep/clips "
    f"--scenes ep/scenes --stage clips --from 9")
run(f"python3 {SK}/scripts/build_video.py ep/plan.json --work ep/clips "
    f"--scenes ep/scenes --stage join -o ep/renders/episode.mp4")
run(f"python3 {SK}/scripts/verify.py ep/renders/episode.mp4 --plan ep/plan.json "
    f"--clips ep/clips --scenes ep/scenes")
```

(`run` and `SK` are the helper defined in SKILL.md — there is no bash kernel, so
shell work goes through `capsule.proc.exec` from the Python kernel.)

`--stage join` concatenates by stream copy and mixes the narration, so it stays
fast no matter how long the episode is. If a clips range does abort, re-run the
same command — finished clips are verified by length and skipped, and a clip cut
off mid-encode is discarded rather than trusted.

If you would rather not chunk, launch the long command detached inside the
sandbox and poll a log instead:

```python
capsule.proc.exec(
    f"nohup setsid python3 {SK}/scripts/build_video.py ep/plan.json --work ep/clips "
    f"--scenes ep/scenes --stage clips > /tmp/render.log 2>&1 &")
# then, in later short calls:
run("tail -5 /tmp/render.log")
```

## Getting the results out

The capsule filesystem is not the deliverable, and the sandbox is disposable.

**Deliver with `export_file`.** Copy the finished master, the covers and the
copy into `/workspace/outputs/`, then call `export_file` on each one — it
returns a permanent link, and records the file as a conversation output so it
renders in the UI. `capsule_download_url` returns a permanent object-storage
link too, so it is also safe to hand over.

The tool that dies with the sandbox is **`capsule_get_url`** — it maps a live
port on the VM, so it 502s the moment the sandbox goes away. Use it to check
your own work in a running preview, never as a deliverable.

```python
run("mkdir -p /workspace/outputs && "
    "cp ep/renders/episode.mp4 ep/covers/*.png ep/*.md /workspace/outputs/ && "
    "ls -la /workspace/outputs/")     # confirm the bytes are actually there
```

`/workspace` is a network-backed mount with asynchronous write-back, so a
multi-megabyte video can still be uploading after `cp` returns. `export_file`
polls the destination before handing back a URL — if it reports the file is not
there yet, wait and call it again rather than assuming the copy failed. Never
infer that a file persisted just because it appears in the local listing.

Alongside the links, show the contact sheet and two or three extracted frames
inline as images, so the user can judge the result without downloading anything.
