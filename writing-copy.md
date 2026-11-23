# Writing and copy for user-facing documents

- Write in a direct, plain, human voice with active sentences and concise labels.
- Avoid AI cliché words such as "delve," "testament," "unleash," "transformative," "game-changing," "seamless," and "revolutionize."
- Avoid formulaic contrasts, unnecessary rules of three, redundant subtitles, helper text that repeats headings, and em dashes.
- Run the `unslop` skill before delivery on new or changed reader-facing prose in this **unslop scope**, the one list other files defer to: `README.md`, `CHANGELOG.md`, `steam-description.md`, website descriptions, and only the `description` of `mod.json`, the `<description>` of `About/About.xml` and the `Description` of a Timberborn `manifest.json`. This holds for every edit to those files, including one-line changelog entries and edits a subagent makes. Preserve facts, names, identifiers, commands, links, code, markup, and data structure. If `unslop` is unavailable, apply these writing rules manually and state in the delivery summary that `unslop` was unavailable. Other writing gets `unslop` only when the user asks.
- Do not include test results or validation status in user-facing documents; readers do not need them. On the subject of testing, a `README.md` covers only build and install instructions.
