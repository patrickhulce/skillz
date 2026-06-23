---
name: describe-it
description: Create structured pull request descriptions following a structured template. Use when the user needs to write a PR description, wants to document their changes for a pull request, or asks to generate a PR summary. Triggers on phrases like "write a PR description", "create PR description", "document my PR", "PR summary", or when the user has finished implementing changes and needs to create a PR. Writes the description to PR.md.
---

# PR Description Writer

Generate clear, comprehensive pull request descriptions using a structured template. Analyze code changes (via `git diff`, `git log`, staged changes) to produce well-organized PR descriptions.

## Workflow

1. Analyze changes using `git diff main...HEAD`, `git log main..HEAD`, and `git status`
2. Draft the PR description following the template below
3. Write the description to `PR.md`
4. If evidence is missing and no tests exist in the PR, ask the user how to proceed

## Template

### Summary

- 1-2 sentences describing the change
- Start with an action verb (Adds, Fixes, Updates, Improves, etc.)
- Focus on what the PR accomplishes, not how
- DO NOT INCLUDE A `### Summary` HEADER, the first text of the description should just be the summary itself.

### Usage

- Concrete examples: commands, code snippets, or step-by-step UI instructions
- Skip for internal refactoring or bug fixes that don't change usage

### Changes

- Bulleted list of specific changes
- Mention specific classes, methods, or files modified
- Group related changes together
- Omit for simple, single-purpose PRs

### Evidence

- Demonstration that the change works as intended
- Acceptable forms: unit tests in the PR, screenshots, videos, command output, deployed previews
- If no actual evidence available, create some by running an example command, opening the dev server with Playwright to create a screenshot, etc.

### References (Optional - only if concrete links exist)

- Links to related issues, design docs, PRDs, or external documentation
- Omit if there are no concrete hyperlinks to provide

## Rules

- Omit optional sections entirely when they don't apply
- Be specific in Changes: use actual class names, file names, method names
- Usage examples must be runnable commands or followable steps
- Always write the final description to `PR.md`

## Example

````markdown
Improves the reliability of identity recognition by introducing a secondary threshold and caching of resolved identities from the prior frame.

### Usage

\```bash
uv run faceswap.py --video-path /path/to/video.mp4 --secondary-identity-threshold=0.5
\```

### Changes

- Added a `detected_identities_cache` dictionary to the `FaceSwapper` class to cache the identities detected in the previous frame.
- Renamed `MINIMUM_IDENTITY_CONFIDENCE` to `PRIMARY_IDENTITY_CONFIDENCE` and introduced `SECONDARY_IDENTITY_CONFIDENCE` which applies when unambiguous.
- Overhauled the `determine_identity` method in the `FaceSwapper` class to incorporate the new identity determination logic, including fallbacks and forced identity assignment.

### Evidence

<video src="https://github.example.com/assets/example-video.mp4" />
````
