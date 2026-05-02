# GlobalTemplates

Reusable templates and instruction files for my development, GitHub, and Steam Workshop workflows.

This repository is the source of truth for shared `.md` and text templates that are used across projects. It keeps documentation, changelog, and publishing templates consistent without duplicating or rewriting the same instructions in every repo.

## Purpose

- Keep global templates in one version-controlled location.
- Make Codex and other AI-assisted workflows use the same source templates.
- Separate repo/GitHub templates from Steam Workshop templates.
- Reduce drift between local project documentation files.
- Make template updates easy to track, review, and reuse.

## Repository Structure

```text
GlobalTemplates/
├── Git/
│   ├── changeLogTemplate.md
│   └── readmeTemplate.md
├── Steam/
│   └── steamDescriptionTeamplate.md
├── AGENTS.md
├── LICENSE
└── README.md
```

> Note: `steamDescriptionTeamplate.md` appears to be intentionally listed as the current filename in this repo. If this is a typo, rename it to `steamDescriptionTemplate.md` and update any Codex or automation references that point to it.

## Templates

| Template | Folder | Output Target | Purpose |
| --- | --- | --- | --- |
| `readmeTemplate.md` | `Git/` | `README.md` | Generates GitHub README files for project repositories. |
| `changeLogTemplate.md` | `Git/` | `CHANGELOG.md` | Generates and updates dated changelog history files. |
| `steamDescriptionTeamplate.md` | `Steam/` | `steamDescription.MD` | Generates Steam Workshop descriptions using Steam BBCode. |

## Recommended Setup

The best way to use these globally is to keep this GitHub repository as the source of truth, then clone or pull it into a stable local templates folder.

Example local setup:

```powershell
git clone https://github.com/KyleMHB/GlobalTemplates.git E:\Coding\Templates
```

To update local templates later:

```powershell
cd E:\Coding\Templates
git pull
```

This keeps the templates available locally while still allowing changes to be tracked in GitHub.

## Codex Usage

In Codex personal instructions, reference these templates by their local path when available.

Suggested mapping:

```md
When creating or updating markdown documentation, use the relevant template from `E:\Coding\Templates` if accessible.

Template mappings:
- README:
  - Target file: `README.md`
  - Template: `E:\Coding\Templates\Git\readmeTemplate.md`
- Changelog:
  - Target file: `CHANGELOG.md`
  - Template: `E:\Coding\Templates\Git\changeLogTemplate.md`
- Steam Workshop description:
  - Target file: `steamDescription.MD`
  - Template: `E:\Coding\Templates\Steam\steamDescriptionTeamplate.md`

Rules:
- Read and follow the relevant template before writing the target file.
- Update existing repo files instead of creating duplicates.
- Create missing target files from the relevant template.
- Do not edit the global templates unless explicitly asked.
- If the local template path is unavailable, report it clearly before using a fallback structure.
```

## GitHub Raw Usage

For cloud environments where `E:\Coding\Templates` is not available, use the raw GitHub file URLs as a fallback.

```text
https://raw.githubusercontent.com/KyleMHB/GlobalTemplates/main/Git/readmeTemplate.md
https://raw.githubusercontent.com/KyleMHB/GlobalTemplates/main/Git/changeLogTemplate.md
https://raw.githubusercontent.com/KyleMHB/GlobalTemplates/main/Steam/steamDescriptionTeamplate.md
```

## Adding New Templates

When adding a new template:

1. Place it in the folder that matches its workflow or target platform.
2. Use a clear filename ending in `Template.md`.
3. Include instructions inside the template, not only placeholder content.
4. Define the expected output file name.
5. Define formatting rules, required sections, and file-management behavior.
6. Update this README with the new template mapping.

Recommended template structure:

```md
# System Instructions: [Template Name]

## Role
Describe what the assistant or tool should act as.

## Output Format Requirements
Define the required format, such as GFM, BBCode, XML, JSON, or plain text.

## Required Structure
List the exact sections or fields the output must contain.

## Execution & File Management
Explain which file should be created or updated and where it should be saved.
```

## Naming Guidelines

- Use descriptive names that explain the target output.
- Prefer `camelCaseTemplate.md` for template files.
- Keep platform-specific templates in platform folders.
- Keep GitHub/repository documentation templates in `Git/`.
- Avoid renaming templates without updating Codex instructions and project references.

## Maintenance Rules

- Keep templates practical and reusable.
- Avoid project-specific details unless the template is meant for a narrow workflow.
- Keep instructions direct and action-oriented.
- Update templates when your workflow changes.
- Keep this README in sync with the folder structure.

## License

Released under the MIT License. See [`LICENSE`](LICENSE) for details.
