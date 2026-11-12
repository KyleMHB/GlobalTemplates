# Template routing

Resolve templates from this checkout or a user/project-configured Templates root. Paths below are relative to that root. When local files are unavailable and network access is allowed, append the relative path to `https://raw.githubusercontent.com/KyleMHB/GlobalTemplates/main/`. Update existing documents without replacing useful project-specific content. Edit source templates only when explicitly requested.

Ordinary templates are explicit opt-in. A changelog template may be inspected and applied automatically only when the matching trigger below is satisfied. An existing `TESTING.md` may be updated automatically when its procedures, expectations, or evidence materially change; creating one requires an explicit request. For an illustrated Workshop page, also read `Steam/workshop-page-guide.md`, which covers artwork and the `Steam/preview-workshop.py` preview.

For RimWorld test-case/harness work or artwork, use the [RimWorld agent read route](Steam/rimworld/agent-guide.md). These are reusable workflow guides, not document templates; read only the matching branch.

Public copy also follows [writing and copy](writing-copy.md).

| Target | Template | Activation | Public copy |
| --- | --- | --- | --- |
| `README.md` | `Git/readme-template.md` | Explicit template-backed request | Yes |
| `CHANGELOG.md` | `Git/change-log-template.md` | Explicit request, or a completed change with useful user, maintainer, or operational impact | Yes |
| `TESTING.md` | `Git/testing-template.md` | Explicit request to create, or material changes to an existing file's procedures, expectations, or evidence | No |
| `steam-description.md` | `Steam/steam-description-template.md` | Explicit template-backed request | Yes |
| `mod.json` | `Steam/wayward/wayward-mod-json-template.md` | Explicit template-backed request | Yes |
| `About/About.xml` | `Steam/rimworld/rimworld-about-xml-template.md` | Explicit template-backed request | Yes |
