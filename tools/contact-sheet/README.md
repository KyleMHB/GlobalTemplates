# Contact sheet

Renders a comparison image of artwork: one row per item, one tile per version, with arrows between versions. The newest version sits on the right with a highlight. The sheet is sized and coloured for posting on Discord.

It needs Python 3.9 or newer, Pillow and, for committed versions, git.

## Use

Run it from the project that holds the art.

~~~bash
python contact_sheet.py -o sheet.png --labels Before After --item "Sunstone array" old.png new.png
~~~

| Option | Meaning |
| --- | --- |
| `-o`, `--output` | Where to write the PNG. Required. |
| `--item LABEL IMAGE...` | A row: its label, then its images, oldest first. Repeat for more rows. |
| `--history COUNT IMAGE...` | A row per image with its last COUNT distinct versions from git, captioned by commit date. |
| `--labels TEXT...` | Column headings, oldest first. One per column. |
| `--title`, `--subtitle`, `--footer` | Optional text. A single row with no title uses its label as the title. |
| `--cell PIXELS` | Tile size. By default it shrinks as columns are added. |
| `--backdrop #hex` | Tile colour behind the art. The default is a mid grey that keeps dark outlines visible. |
| `--accent #hex` | Arrow and highlight colour. By default each row takes it from its own art. |

An image is one of:

- a file path;
- the name of an image tracked by git, such as `SunstoneArray`. When several files share the name, the one under `Textures/` wins;
- `REV:path`, a committed version, such as `b634a49:Textures/Things/Building/Misc/SunstoneArray.png`.

Rows with fewer versions sit to the right, so the newest versions line up. Two neighbouring versions with identical files get an `=` in place of the arrow and the word "unchanged".

The `contact-sheet` skill in `.agents/skills` walks an agent through choosing versions and rendering.
