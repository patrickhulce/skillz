---
name: dogfood-it
description: Test documentation and tutorials by following their instructions step-by-step, logging every error, unclear step, or workaround to a FEEDBACK.md file. Use when the user asks to test docs, validate a tutorial, try out a guide, or follow any set of written instructions.
---

# Dogfood It (Test Documentation & Other Manual Flows)

Follow a piece of documentation or tutorial step-by-step, execute each instruction, and record structured feedback about anything that goes wrong, is unclear, or requires a workaround.

## Inputs

The user provides one or more of:

- A path to a markdown file
- A URL to a documentation page
- A directory of markdown files to test in sequence
- [Optional] Context about what has already been completed or the current execution environment

## Setup

1. **Read the documentation.** If given a URL, fetch it with `WebFetch`. For a local path, read the file directly.

2. **Create FEEDBACK.md** in the current working directory. Initialize it with the header template below.

3. **Parse the doc into an ordered list of steps.** Steps are any instruction the reader is expected to act on: commands to run, files to create/edit, configurations to set, links to visit, etc. Number them for reference.

## Execution Loop

For each step:

1. **Log the step** you are about to attempt (quote or paraphrase the instruction).
2. **Attempt it.** Run commands, create files, visit linked URLs — whatever the doc says.
3. **Evaluate the outcome:**
    - **Success** — move on silently (no FEEDBACK entry needed).
    - **Failure / unexpected result / unclear instruction** — append a feedback entry (see format below) and then try to work around it so you can keep going.
4. **Continue** to the next step regardless of outcome. The goal is to get as far as possible and capture all issues, not to stop at the first failure.

After all steps are attempted, append a **Summary** section to FEEDBACK.md.

## FEEDBACK.md Format

Initialize the file with:

```markdown
# Documentation Test Feedback

| Field           | Value                                       |
| --------------- | ------------------------------------------- |
| **Source**      | `<path or URL of the doc>`                  |
| **Tested on**   | `<date>`                                    |
| **Environment** | `<OS, runtime versions, anything relevant>` |

---
```

### Per-Issue Entry

Append one of these each time something goes wrong or is unclear:

```markdown
## Issue N: <short title>

| Field                       | Detail                                                                         |
| --------------------------- | ------------------------------------------------------------------------------ |
| **Step / instruction**      | <quote or paraphrase of the step you were following>                           |
| **Expected / unclear**      | <what you expected to happen, or what was ambiguous>                           |
| **Actual result**           | <what actually happened — include error output, truncated if very long>        |
| **Workaround / assumption** | <what you did to keep going, or "Blocked — could not continue past this step"> |
```

### Summary Section

Append at the end:

```markdown
---

## Summary

- **Steps attempted**: N
- **Steps succeeded**: N
- **Issues logged**: N
- **Blocked**: Yes / No (and at which step, if so)

### Recommendations

<Bulleted list of the highest-impact fixes the doc author should make.>
```

## Guidelines

- **Be literal.** Follow instructions exactly as written. If the doc says `pip install foo`, run exactly that — don't silently substitute `pip3` or `conda`. If the literal command fails, log the issue and _then_ try the workaround.
- **Capture error output.** Include the relevant portion of stderr/stdout in the "Actual result" field. Truncate to ~20 lines if it's very long and note that it was truncated.
- **Assume a fresh reader's perspective.** If a step requires context that wasn't provided earlier in the doc, that's an issue worth logging (e.g., "this step assumes tool X is installed, but installation was never mentioned").
- **Don't fix the docs.** Your job is to test and report, not to edit the source documentation.
- **Time-box commands.** If a command hangs for more than 5 minutes with no output, kill it and log a timeout issue.
- **Visit linked URLs.** If the doc links to a URL, visit it and log the result. If it's a relative URL, make sure the local file exists and is accessible.
- **Credentials / secrets.** Never log tokens, passwords, or secrets in FEEDBACK.md. Redact them as `<REDACTED>`.

## Placeholder Assets & Strings

Documentation often says things like "use your username here" or "upload an image" without providing concrete values. Don't stop and ask — substitute a sensible placeholder, log the substitution as an assumption in FEEDBACK.md (so the doc author can decide whether to spell it out), and keep going.

Use the following defaults:

### Names / usernames

Use `$USER`:

```bash
USERNAME="$USER"
```

This works for any step that wants a generic identity (paths under `/home/$USER`, service owners, job names, etc.).

### Generic images

Use [picsum.photos](https://picsum.photos/) for placeholder images. The path is `/<width>/<height>`:

- `https://picsum.photos/200/300` — 200x300 portrait
- `https://picsum.photos/600/400` — 600x400 landscape
- `https://picsum.photos/200/300?grayscale` — grayscale variant
- `https://picsum.photos/seed/<seed>/200/300` — deterministic image (use a seed when the test needs reproducibility)

### Generic videos

Use [lorem.video](https://lorem.video/) for placeholder videos. The path encodes parameters separated by underscores; later parameters override earlier ones, and unknown parameters are silently ignored:

- `https://lorem.video/720p` — default 720p H.264 MP4
- `https://lorem.video/1280x720` — custom resolution
- `https://lorem.video/720p_h264_10s` — short 10-second clip for quick prototyping
- `https://lorem.video/720p_av1` — AV1 codec
- `https://lorem.video/1080p_vp9_30fps_30s_25crf_opus_128kbps.webm` — VP9/Opus in WebM
- `https://lorem.video/cat_480p_h264_30fps_15s_26crf_aac_96kbps.mp4` — mobile-style low-bitrate clip
- `https://lorem.video/bunny_novideo_30s_aac_128kbps.mp4` — audio-only

When a step calls for a specific codec, container, resolution, frame rate, or duration, **encode it into the URL** rather than reaching for a different sample — that's exactly what lorem.video is for. Available knobs: resolutions (`240p`–`4k` or `WxH`), video codecs (`h264`, `h265`, `vp9`, `av1`, `novideo`), audio codecs (`aac`, `opus`, `vorbis`, `noaudio`), containers (`.mp4`, `.webm`), source names (`bunny`, `cat`, `corgi`, `test`).

### Logging the substitution

Whenever you swap in a placeholder, add an entry like:

```markdown
## Issue N: Step did not specify a sample <asset>

| Field                       | Detail                                                              |
| --------------------------- | ------------------------------------------------------------------- |
| **Step / instruction**      | "Upload a video to the service"                                     |
| **Expected / unclear**      | No sample video URL or path was provided.                           |
| **Actual result**           | N/A — needed an asset to proceed.                                   |
| **Workaround / assumption** | Used `https://lorem.video/720p_h264_10s` as a placeholder. The doc should link to a canonical sample or describe the expected format. |
```
