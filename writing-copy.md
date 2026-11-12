# Writing and copy for user-facing documents

- Write in a direct, plain, human voice with active sentences and concise labels.
- Avoid AI cliché words such as "delve," "testament," "unleash," "transformative," "game-changing," "seamless," and "revolutionize."
- Avoid formulaic contrasts, unnecessary rules of three, redundant subtitles, helper text that repeats headings, and em dashes.
- Use the `unslop` skill (for `README.md`, `CHANGELOG.md` and `steam-description.md`) on reader-facing prose before delivery. Preserve facts, names, identifiers, commands, links, code, markup, and data structure. In `mod.json`, process only `description`; in `About/About.xml`, process only `<description>`. If `unslop` is unavailable, apply these writing rules manually and state in the delivery summary that `unslop` was unavailable. Do not use `unslop` for anything other than the listed template file items unless instructed.
- Do not include test results or validation status in user-facing documents; readers do not need them. On the subject of testing, a `README.md` covers only build and install instructions.
