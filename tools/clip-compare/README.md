# Clip compare

Joins two or more video clips into one comparison video: each clip in its own panel under a label, oldest first. The output is a silent MP4 sized for posting on Discord.

It needs Python 3.9 or newer and FFmpeg. FFmpeg is looked for at `--ffmpeg`, then on PATH, then in `tools/rimworld-dev-tests/work/ffmpeg/`.

## Use

~~~bash
python clip_compare.py -o compare.mp4 --clip "First take" old.mp4 6 6.3 --clip Now new.mp4 8.5 10 1.5 --still 1.2
~~~

| Option | Meaning |
| --- | --- |
| `-o`, `--output` | Where to write the MP4. Required. |
| `--clip LABEL FILE [START [LENGTH [ZOOM]]]` | A panel: its label, the video, where to start in seconds, how many seconds to take, and how far to zoom on the centre of the frame. Repeat for each clip, oldest first. START defaults to 0, LENGTH to the rest of the file and ZOOM to 1. |
| `--length SECONDS` | Length of the output. The default is the longest clip. |
| `--panel WIDTHxHEIGHT` | Size of each panel. The default is `960x540`. In `feature`, the newest clip's panel is this size times the number of older clips. |
| `--layout NAME` | `row`, the default, puts the panels side by side. `stack` puts them above each other, which reads better on a phone. `feature` puts the older clips in a row and the newest beneath them at the row's full width. |
| `--still SECONDS` | Also write a PNG of the frame at this time, beside the MP4. |
| `--ffmpeg PATH` | The FFmpeg to use. |

A clip shorter than the output loops. The first label is amber, the last is green and any between are grey. The tool warns when the file is over 10 MB, Discord's upload limit without Nitro.

The `clip-compare` skill in `.agents/skills` walks an agent through choosing the moments and checking the result.
