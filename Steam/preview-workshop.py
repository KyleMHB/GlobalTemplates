"""Render Steam description BBCode to a local HTML preview (Python standard library)."""
import argparse
import html
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


def render(text, root, mappings):
    warnings, stack, output = [], [], []
    pairs = {'h1': 'h1', 'h2': 'h2', 'h3': 'h3', 'b': 'strong',
             'i': 'em', 'u': 'u', 'strike': 's', 'list': 'ul', 'olist': 'ol'}

    def image_source(url):
        for prefix, folder in mappings:
            if url.startswith(prefix):
                relative = unquote(url[len(prefix):]).split('?', 1)[0]
                path = (folder / relative).resolve()
                if not path.is_relative_to(folder):
                    raise ValueError('Image mapping escapes its folder: ' + url)
                if not path.is_file():
                    raise ValueError('Missing mapped image: ' + str(path))
                return path.as_uri()
        if urlsplit(url).scheme in ('http', 'https'):
            warnings.append('Remote image (not checked): ' + url)
            return url
        if urlsplit(url).scheme:
            raise ValueError('Unsupported image URL: ' + url)
        path = (root / unquote(url)).resolve()
        if not path.is_file():
            raise ValueError('Missing image: ' + str(path))
        return path.as_uri()

    # Images are consumed whole so their URL cannot be interpreted as BBCode.
    tokens = re.split(r'(\[img\].*?\[/img\]|\[url\][^\[\]\n]*\[/url\]|\[/?[a-zA-Z][^\]\n]*\]|\[\*\])',
                      text, flags=re.S | re.I)
    for token in tokens:
        lowered = token.lower()
        if lowered.startswith('[img]') and lowered.endswith('[/img]'):
            src = image_source(token[5:-6].strip())
            output.append('<img alt="Workshop illustration" src="' + html.escape(src, quote=True) + '">')
        elif lowered.startswith('[url]') and lowered.endswith('[/url]'):
            url = token[5:-6].strip()
            if urlsplit(url).scheme not in ('http', 'https'):
                raise ValueError('Use an absolute HTTP(S) link: ' + token)
            output.append('<a href="' + html.escape(url, quote=True) + '">' + html.escape(url) + '</a>')
        elif token == '[*]':
            if stack and stack[-1] == 'li':
                output.append('</li>'); stack.pop()
            if not stack or stack[-1] not in ('list', 'olist'):
                raise ValueError('List item outside a list')
            output.append('<li>'); stack.append('li')
        elif re.fullmatch(r'\[/?[^\]]+\]', token):
            closing = token.startswith('[/')
            name, _, value = token[2 if closing else 1:-1].partition('=')
            name = name.lower()
            if name in ('list', 'olist') and closing and stack and stack[-1] == 'li':
                output.append('</li>'); stack.pop()
            if name == 'hr':
                if not closing:
                    output.append('<hr>')
            elif name in pairs or name == 'url':
                tag = pairs.get(name, 'a')
                if closing:
                    if not stack or stack.pop() != name:
                        raise ValueError('Unbalanced BBCode at ' + token)
                    output.append('</' + tag + '>')
                else:
                    if name == 'url':
                        if urlsplit(value).scheme not in ('http', 'https'):
                            raise ValueError('Use an absolute HTTP(S) link: ' + token)
                        output.append('<a href="' + html.escape(value, quote=True) + '">')
                    else:
                        output.append('<' + tag + '>')
                    stack.append(name)
            else:
                warnings.append('Unsupported markup shown literally: ' + token)
                output.append(html.escape(token))
        else:
            output.append(html.escape(token))
    if stack:
        raise ValueError('Unclosed BBCode: ' + ', '.join(stack))
    return ''.join(output), warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='steam-description.md containing BBCode')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--title', default='Workshop description preview')
    parser.add_argument('--width', type=int, default=636, help='Preview column width in pixels')
    parser.add_argument('--thumbnail', type=Path, help='Workshop item thumbnail/icon (local PNG, JPG, GIF or WebP)')
    parser.add_argument('--gallery', type=Path, action='append', default=[],
                        help='Gallery image in display order; repeat for each local image')
    parser.add_argument('--game', default='', help='Game name displayed above the item title')
    parser.add_argument('--author', default='', help='Creator name displayed in the summary panel')
    parser.add_argument('--image-map', action='append', default=[], metavar='URL_PREFIX=LOCAL_FOLDER',
                        help='Repeat to resolve hosted image URLs to local files; use a trailing slash in the prefix')
    args = parser.parse_args()
    if args.width < 240:
        parser.error('--width must be at least 240')
    mappings = []
    for mapping in args.image_map:
        prefix, separator, folder = mapping.rpartition('=')
        if not separator or not prefix or not folder:
            parser.error('--image-map requires URL_PREFIX=LOCAL_FOLDER')
        mappings.append((prefix, Path(folder).resolve()))
    mappings.sort(key=lambda item: len(item[0]), reverse=True)
    source, target = args.source.resolve(), args.output.resolve()
    if source == target:
        parser.error('Output must differ from the source')
    try:
        text = source.read_text(encoding='utf-8-sig')
        body, warnings = render(text, source.parent, mappings)
    except ValueError as error:
        parser.error(str(error))
    # Steam counts BBCode tags toward its 8,000-character description limit.
    length = len(text.strip())
    if length > 8000:
        warnings.append(f'Description is {length:,} characters; Steam allows 8,000 including BBCode')
    title = html.escape(args.title)
    def media_image(path, alt, attributes=''):
        path = path.resolve()
        if not path.is_file():
            parser.error('Missing media image: ' + str(path))
        if path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
            parser.error('Use PNG, JPG, GIF or WebP media: ' + str(path))
        return '<img src="' + html.escape(path.as_uri(), quote=True) + '" alt="' + html.escape(alt, quote=True) + '" ' + attributes + '>'

    media = ''
    if args.thumbnail or args.gallery:
        gallery_images = [media_image(path, f'Gallery image {i + 1}: {path.stem}')
                          for i, path in enumerate(args.gallery)]
        viewer = gallery_images[0].replace('<img ', '<img id="gallery-image" ', 1) if gallery_images else '<p>No gallery images supplied.</p>'
        strip = ''.join('<button type="button" class="gallery-thumb" aria-label="Show gallery image ' + str(i + 1) +
                        '" aria-pressed="' + ('true' if i == 0 else 'false') + '">' + img + '</button>'
                        for i, img in enumerate(gallery_images))
        controls = ('<div class="gallery-controls"><button type="button" id="previous">Previous</button>'
                    '<span id="gallery-position" aria-live="polite">1 / ' + str(len(gallery_images)) +
                    '</span><button type="button" id="next">Next</button></div>') if len(gallery_images) > 1 else ''
        thumbnail = media_image(args.thumbnail, 'Workshop thumbnail for ' + args.title) if args.thumbnail else '<p>No Workshop thumbnail supplied.</p>'
        creator = '<p class="creator">Created by ' + html.escape(args.author) + '</p>' if args.author else ''
        breadcrumb = '<p class="breadcrumb">' + html.escape(args.game) + ' &gt; Workshop</p>' if args.game else ''
        media = (breadcrumb + '<header><h1 class="item-title">' + title + '</h1></header>'
                 '<div class="page-tab">Description</div><div class="media-layout">'
                 '<section class="gallery" aria-label="Workshop gallery"><div class="gallery-viewer">' + viewer +
                 '</div><div class="gallery-strip" aria-label="Choose gallery image">' + strip + '</div>' + controls +
                 '</section><aside class="item-summary" aria-label="Workshop item summary">' + thumbnail +
                 '<h2>' + title + '</h2>' + creator + '</aside></div>')
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>''' + title + '''</title><style>
body{margin:0;background:#171f29;color:#d6d7d8;font:15px/1.55 Arial,sans-serif}
main{max-width:''' + str(args.width + 312 if media else args.width) + '''px;margin:30px auto;padding:0 16px}
article{max-width:''' + str(args.width) + '''px;white-space:pre-line;overflow-wrap:anywhere}img{max-width:100%;height:auto;display:block;margin:16px auto}
h1,h2,h3,ul,ol{white-space:normal}h1{font-size:23px;color:#fff;line-height:1.3;margin:30px 0 12px}
h2{font-size:19px;color:#e9cf83;line-height:1.3;margin:28px 0 10px}
a{color:#78bce7}li{margin:8px 0}em{color:#b9c3cd}
.preview-note{font-size:13px;color:#b9c3cd;border-bottom:1px solid #465463;padding-bottom:12px;margin-bottom:24px}
.breadcrumb{font-size:13px;color:#b9c3cd;margin-bottom:4px}.item-title{font-size:28px;font-weight:400;margin:0 0 32px;overflow-wrap:anywhere}
.page-tab{color:#fff;border-bottom:3px solid #66c0f4;width:max-content;padding:0 0 6px;margin-bottom:12px}
.media-layout{display:grid;grid-template-columns:minmax(0,1fr) 268px;gap:16px;background:#243e55;padding:14px;margin-bottom:28px;align-items:start}
.gallery{min-width:0}.gallery-viewer{aspect-ratio:16/9;background:#101822;display:grid;place-items:center;overflow:hidden}
.gallery-viewer img{width:100%;height:100%;object-fit:contain;margin:0;min-height:0}.gallery-viewer p{padding:20px;color:#b9c3cd}
.gallery-strip{display:flex;gap:6px;overflow-x:auto;background:#101822;padding:6px;margin-top:4px}
button{font:inherit;color:#d6d7d8;background:#23394d;border:1px solid #476078;cursor:pointer}
button:hover{background:#36536c}button:focus-visible{outline:2px solid #fff;outline-offset:2px}
.gallery-thumb{flex:0 0 112px;height:67px;padding:2px;border:2px solid transparent}
.gallery-thumb[aria-pressed="true"]{border-color:#66c0f4}.gallery-thumb img{width:100%;height:100%;object-fit:contain;margin:0}
.gallery-controls{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:8px;font-size:13px}
.gallery-controls button{min-height:36px;padding:4px 12px}.item-summary img{width:100%;margin:0 0 12px}
.item-summary h2{font-size:16px;margin:0 0 8px;color:#fff}.creator{font-size:13px;color:#b9c3cd;margin:0}
::selection{background:#66c0f4;color:#101822}*{scrollbar-color:#526a80 #101822}
@media(max-width:700px){.media-layout{grid-template-columns:minmax(0,1fr)}.item-summary{max-width:268px}.item-title{font-size:24px}}
</style></head><body><main><div class="preview-note">Local approximation · ''' + str(args.width) + ''' px description column · Check the published Steam page separately.</div>''' + media + '<article aria-label="Workshop description">' + body + '''</article></main>
<script>
const thumbs = [...document.querySelectorAll('.gallery-thumb')];
const image = document.getElementById('gallery-image');
let selected = 0;
function showGallery(index) {
  selected = (index + thumbs.length) % thumbs.length;
  const source = thumbs[selected].querySelector('img');
  image.src = source.src;
  image.alt = source.alt;
  thumbs.forEach((button, i) => button.setAttribute('aria-pressed', String(i === selected)));
  const position = document.getElementById('gallery-position');
  if (position) position.textContent = `${selected + 1} / ${thumbs.length}`;
  thumbs[selected].scrollIntoView({block: 'nearest', inline: 'nearest'});
}
thumbs.forEach((button, index) => button.addEventListener('click', () => showGallery(index)));
document.getElementById('previous')?.addEventListener('click', () => showGallery(selected - 1));
document.getElementById('next')?.addEventListener('click', () => showGallery(selected + 1));
document.querySelector('.gallery')?.addEventListener('keydown', event => {
  if (thumbs.length && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) {
    event.preventDefault();
    showGallery(selected + (event.key === 'ArrowRight' ? 1 : -1));
    thumbs[selected].focus({preventScroll: true});
  }
});
</script></body></html>'''
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding='utf-8')
    print('Created ' + str(target))
    print(f'Description length: {length:,} of 8,000 characters')
    for warning in dict.fromkeys(warnings):
        print('Warning: ' + warning)


if __name__ == '__main__':
    main()
