# GlobalTemplates

Reusable templates and instruction files for my development, GitHub, and Steam Workshop workflows.

This repository is the source of truth for shared `.md` and text templates that are used across projects. It keeps documentation, changelog, and publishing templates consistent without duplicating or rewriting the same instructions in every repo.

## Purpose

- Keep global templates in one version-controlled location.
- Make Codex and other AI-assisted workflows use the same source templates.
- Separate repo/GitHub templates from Steam Workshop templates.
- Reduce drift between local project documentation files.
- Make template updates easy to track, review, and reuse.

The best way to use these globally is to keep this GitHub repository as the source of truth, then clone or pull it into a stable local templates folder.

## Agent Usage

In Codex personal instructions, reference these templates by their local path when available.

```md
Rules:
- Read and follow the relevant template before writing the target file.
- Update existing repo files instead of creating duplicates.
- Create missing target files from the relevant template.
- Do not edit the global templates unless explicitly asked.
- If the local template path is unavailable, report it clearly before using a fallback structure.
```

## GitHub Raw Usage

For cloud environments where a local repo is not available, use the raw GitHub file URLs as a fallback.

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

## Contributing & Forking Policy
Contributions, issues, and feature requests are welcome!
**Forking Policy:** If your fork primarily consists of bug fixes or feature additions that align with the core vision of this repo, I reserve the right to request that your changes be submitted as a Pull Request to my existing codebase rather than being published as a completely separate standalone release.

## License

Released under the MIT License. See [`LICENSE`](LICENSE) for details.

**Attribution Requirement:** You are free to use and modify this code, provided that you credit me and link back to this project in any release or publically facing repo.
