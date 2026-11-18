"""Manual web generation: pack a job's inputs for a person to upload, then ingest the one result they drop back.
Never edits project state and never drives a provider's web app."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from media import decode_command, fresh_output, probe, video_duration

EXTENSIONS = {'image': ('.png', '.jpg', '.jpeg', '.webp'), 'video': ('.mp4', '.mov')}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def slug(text):
    return re.sub(r'\W+', '-', str(text).lower()).strip('-') or 'input'


def pack(job, root, out_dir):
    """Copy inputs to OUT_DIR/NN-<slot>.<ext>, write request.md and an empty output/. Validates before writing."""
    root, out_dir = Path(root), Path(out_dir)
    if not (isinstance(job, dict) and job.get('model') and job.get('prompt')): raise ValueError('job: model and prompt are required')
    inputs = job.get('inputs', [])  # a text-only request has none
    if not isinstance(inputs, list): raise ValueError('job: inputs must be a list')
    if out_dir.exists(): raise FileExistsError(f'Choose a new pack folder: {out_dir}')
    sources = []
    for item in inputs:
        src = root / item['path']
        if not src.is_file(): raise ValueError(f"input not found: {item['path']}")
        sources.append(src)
    out_dir.mkdir(parents=True)
    records, rows = [], []
    for n, (item, src) in enumerate(zip(inputs, sources), 1):
        name = f"{n:02d}-{slug(item.get('slot'))}{src.suffix.lower()}"
        shutil.copy2(src, out_dir / name)
        records.append({'path': item['path'], 'packed': name, 'sha256': sha256(src)})
        rows.append(f"| {name} | {item.get('slot', '')} | {item.get('purpose', '')} |")
    output = job.get('output') or {}
    lines = [f"# {job.get('provider', 'Provider')} — {job['model']}", '',
             'Generate this by hand in the provider web app. Do not automate the web app.', '', '## Settings', '',
             *[f'- {k}: {v}' for k, v in (job.get('settings') or {}).items()], '', '## Inputs (upload in this order)', '',
             *(['| file | slot | purpose |', '|---|---|---|', *rows] if rows else ['No input files: text only.']), '', '## Prompt', '', '```text', job['prompt'], '```', '',
             'After pasting, check that every reference tag in the prompt links to its uploaded file: a tag left as plain text '
             'means the model never sees that input. Note how many images and videos the app accepted.', '',
             '## Result', '', f"Expected: {output.get('kind', 'file')}. {output.get('notes', '')}".rstrip(),
             '', 'Put exactly one result file in `output/`.', '']
    (out_dir / 'request.md').write_text('\n'.join(lines))
    (out_dir / 'output').mkdir()
    return records


def ingest(pack_dir, dest, kind):
    """Verify the one result in PACK_DIR/output/ decodes as KIND, copy it to DEST and describe it."""
    exts = EXTENSIONS[kind]
    files = [p for p in sorted((Path(pack_dir) / 'output').iterdir()) if p.is_file() and not p.name.startswith('.')]
    if len(files) != 1: raise ValueError(f'output/ must contain exactly one result file; found {len(files)}')
    src = files[0]
    if src.suffix.lower() not in exts:
        raise ValueError(f"expected {kind} file ({', '.join(exts)}); got {src.suffix or 'no extension'}")
    try:
        info = probe(src)
        stream = next(s for s in info['streams'] if s.get('codec_type') == 'video')
        # ffprobe exits 0 on a corrupt image; a decoded frame and real dimensions are the evidence
        if not (int(stream.get('nb_read_frames') or 0) > 0 and stream.get('width') and stream.get('height')): raise ValueError
        # content, not just the extension, must match the kind
        if kind == 'image' and stream.get('codec_name') not in ('png', 'mjpeg', 'webp'): raise ValueError
        if kind == 'video' and not {'mov', 'mp4'} & set(info['format']['format_name'].split(',')): raise ValueError
        # a truncated JPEG or faststart MP4 still probes; a strict full decode catches it
        cmd = decode_command(src)
        subprocess.run(cmd[:cmd.index('-i')] + ['-err_detect', 'explode'] + cmd[cmd.index('-i'):], check=True,
                       capture_output=True)
        duration = fps = None
        if kind == 'video':
            num, den = (int(x) for x in stream['r_frame_rate'].split('/'))
            duration, fps = video_duration(src), round(num / den, 3)
    except (subprocess.CalledProcessError, StopIteration, ValueError, KeyError, ZeroDivisionError):
        raise ValueError(f'cannot decode {src.name} as {kind}') from None
    dest = fresh_output(dest)
    shutil.copy2(src, dest)
    return {'dest': str(dest), 'sha256': sha256(dest), 'kind': kind, 'width': stream['width'],
            'height': stream['height'], 'duration': duration, 'fps': fps}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    q = sub.add_parser('pack', help='job.json -> upload folder with request.md (run from the project directory)')
    q.add_argument('job'); q.add_argument('out_dir')
    q = sub.add_parser('ingest', help='one result in PACK_DIR/output/ -> verified copy at DEST')
    q.add_argument('pack_dir'); q.add_argument('dest'); q.add_argument('--kind', choices=sorted(EXTENSIONS), required=True)
    a = p.parse_args()
    try:
        if a.action == 'pack': result = pack(json.loads(Path(a.job).read_text()), Path.cwd(), a.out_dir)
        else: result = ingest(a.pack_dir, a.dest, a.kind)
    except (ValueError, FileExistsError, FileNotFoundError) as e:
        sys.exit(f'error: {e}')
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__': main()
