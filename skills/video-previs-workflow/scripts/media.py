"""FFmpeg helpers. Commands use argument arrays, preserve inputs, and reject output overwrites."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile


def fresh_output(path):
    path = Path(path).resolve()
    if path.exists(): raise FileExistsError(f'Choose a new output path: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def run(args):
    subprocess.run([str(x) for x in args], check=True)


def probe(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames',
        '-show_streams', '-show_format', '-of', 'json', str(path)], text=True))


SPEED_RANGE = (0.9, 1.1)  # beyond this, generated motion visibly rushes or drags: re-cut or regenerate


def clip_command(source, output, frames, fps, width, height, start=0.0, speed=1.0):
    seek = ['-ss', str(start)] if start > 0 else []
    retime = f'setpts=(PTS-STARTPTS)/{speed},' if speed != 1 else ''
    return ['ffmpeg', '-v', 'error', '-n', *seek, '-i', str(source), '-an', '-vf',
        f'{retime}fps={fps},scale={width}:{height}:force_original_aspect_ratio=decrease,'
        f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration={frames/fps}',
        '-frames:v', str(frames), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(output)]


def decode_command(path):
    return ['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-f', 'null', '-']


def assemble(manifest_path, output):
    manifest_path = Path(manifest_path).resolve()
    data = json.loads(manifest_path.read_text())
    for name in ('fps', 'width', 'height'):
        if type(data.get(name)) is not int or data[name] <= 0: raise ValueError(f'invalid {name}')
    if data['width'] % 2 or data['height'] % 2: raise ValueError('dimensions must be even')
    if not isinstance(data.get('clips'), list) or not data['clips']: raise ValueError('clips required')
    resolve = lambda p: (manifest_path.parent / p).resolve()
    for clip in data['clips']:
        if type(clip.get('frames')) is not int or clip['frames'] <= 0: raise ValueError('positive frames required')
        if not resolve(clip['path']).is_file(): raise FileNotFoundError(clip['path'])
        start, speed = clip.get('start', 0), clip.get('speed', 1)
        if type(start) not in (int, float) or start < 0: raise ValueError('start must be >= 0')
        if type(speed) not in (int, float) or not SPEED_RANGE[0] <= speed <= SPEED_RANGE[1]:
            raise ValueError('speed must be within 0.9-1.1')
        if clip.get('dialogue') and speed != 1: raise ValueError('dialogue clips must keep speed 1.0')
    # Audio must already be mixed to the approved timeline. Clip audio is intentionally discarded.
    for key in ('audio', 'subtitles'):
        if data.get(key) and not resolve(data[key]).is_file(): raise FileNotFoundError(data[key])
    output = fresh_output(output)
    total = sum(c['frames'] for c in data['clips'])
    with tempfile.TemporaryDirectory(prefix='video-edit-') as temp:
        root = Path(temp)
        for i, clip in enumerate(data['clips']):
            run(clip_command(resolve(clip['path']), root / f'{i}.mp4', clip['frames'], data['fps'], data['width'],
                             data['height'], clip.get('start', 0), clip.get('speed', 1)))
        (root / 'clips.txt').write_text(''.join(f"file '{i}.mp4'\n" for i in range(len(data['clips']))))
        run(['ffmpeg', '-v', 'error', '-n', '-f', 'concat', '-safe', '1', '-i', root / 'clips.txt', '-c', 'copy', root / 'joined.mp4'])
        cmd = ['ffmpeg', '-v', 'error', '-n', '-i', root / 'joined.mp4']
        next_index = 1
        if data.get('audio'):
            cmd += ['-i', resolve(data['audio'])]; audio_index = next_index; next_index += 1
        if data.get('subtitles'):
            cmd += ['-i', resolve(data['subtitles'])]; subtitle_index = next_index
        cmd += ['-map', '0:v:0', '-c:v', 'copy']
        if data.get('audio'): cmd += ['-map', f'{audio_index}:a:0', '-af', 'apad', '-c:a', 'aac']
        if data.get('subtitles'): cmd += ['-map', f'{subtitle_index}:s:0', '-c:s', 'mov_text']
        cmd += ['-t', str(total / data['fps']), '-movflags', '+faststart', output]
        run(cmd)
    info = probe(output)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    if int(video.get('nb_read_frames', -1)) != total: raise RuntimeError('Output frame count differs from timeline; inspect output')
    run(decode_command(output))
    print(json.dumps(info, indent=2))


def sample_times(duration, points):
    if points < 2: raise ValueError('points must be >= 2')
    times = [duration * i / (points - 1) for i in range(points)]
    times[-1] = max(0, duration - 0.05)  # seeking to the exact end returns no frame
    return times


def clamp_times(times, duration):
    last = max(0, duration - 0.05)  # seeking to the exact end returns no frame
    return [min(max(t, 0), last) for t in times]


def video_duration(path):
    info = probe(path)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    # Generated clips can carry longer audio, so prefer the video stream's own duration.
    return float(video.get('duration') or info['format']['duration'])


def pair(top, bottom, output, points=5, times=None):
    """Two-row contact sheet: top row from `top`, bottom row from `bottom`, at the same relative times,
    or at the given seconds (event times), each clamped to its own source."""
    if times is not None and len(times) < 2: raise ValueError('times must list 2 or more seconds')
    if times is not None: points = len(times)
    output = fresh_output(output)
    with tempfile.TemporaryDirectory(prefix='video-pair-') as temp:
        frames = []
        for row, source in enumerate((top, bottom)):
            duration = video_duration(source)
            for i, t in enumerate(clamp_times(times, duration) if times is not None else sample_times(duration, points)):
                frame = Path(temp) / f'{row}-{i}.png'
                run(['ffmpeg', '-v', 'error', '-n', '-ss', f'{t:.3f}', '-i', source, '-frames:v', '1',
                     '-vf', 'scale=270:480:force_original_aspect_ratio=decrease,pad=270:480:(ow-iw)/2:(oh-ih)/2', frame])
                frames.append(frame)
        inputs = [x for f in frames for x in ('-i', f)]
        rows = ''.join(f'[{i}]' for i in range(points)) + f'hstack={points}[t];' + \
            ''.join(f'[{points + i}]' for i in range(points)) + f'hstack={points}[b];[t][b]vstack'
        run(['ffmpeg', '-v', 'error', '-n', *inputs, '-filter_complex', rows, output])


CELL = 'scale=270:480:force_original_aspect_ratio=decrease,pad=270:480:(ow-iw)/2:(oh-ih)/2,setsar=1'


def current_keyframe(shot):
    """The approved start keyframe, else the latest pending one, else None."""
    starts = [k for k in shot.get('keyframes') or [] if isinstance(k, dict) and k.get('kind') == 'start']
    approved = [k for k in starts if k.get('approval') == 'approved']
    pending = [k for k in starts if k.get('approval') == 'pending']
    return approved[0] if approved else (pending[-1] if pending else None)


def continuity_rows(state):
    """One row per role used by 2+ shots that have a current keyframe, in first-appearance order."""
    rows = {}
    for shot in state.get('shots') or []:
        key = current_keyframe(shot)
        if key is None: continue
        for role in dict.fromkeys(r for r in (shot.get('object_roles') or {}).values() if isinstance(r, str)):
            row = rows.setdefault(role, {'role': role, 'shots': [], 'paths': [], 'keyframe_sha256': {}})
            row['shots'].append(shot['id']); row['paths'].append(key['path']); row['keyframe_sha256'][shot['id']] = key.get('sha256')
    return [r for r in rows.values() if len(r['shots']) > 1]


def continuity(state_path, output):
    """Contact sheet: a row of current keyframes for every role shared by 2+ shots. Returns the row legend."""
    state_path = Path(state_path).resolve()
    rows = continuity_rows(json.loads(state_path.read_text()))
    if not rows: raise ValueError('no role appears in 2+ shots with keyframes')
    output = fresh_output(output)
    paths = [p for r in rows for p in r['paths']]
    width = 270 * max(len(r['shots']) for r in rows)
    graph, n = [], 0
    for i, r in enumerate(rows):  # every row has 2+ cells, so hstack always has 2+ inputs
        graph += [f'[{n + j}:v]{CELL}[c{n + j}]' for j in range(len(r['shots']))]
        cells = ''.join(f'[c{n + j}]' for j in range(len(r['shots'])))
        graph.append(f'{cells}hstack={len(r["shots"])},pad={width}:480:0:0[r{i}]')
        n += len(r['shots'])
    graph.append(''.join(f'[r{i}]' for i in range(len(rows))) + (f'vstack={len(rows)}' if len(rows) > 1 else 'null'))
    run(['ffmpeg', '-v', 'error', '-n', *[x for p in paths for x in ('-i', state_path.parent / p)],
         '-filter_complex', ';'.join(graph), '-frames:v', '1', output])
    return [{'role': r['role'], 'shots': r['shots'], 'keyframe_sha256': r['keyframe_sha256']} for r in rows]


def sheet(images, output, cols=2, cell=(270, 480)):
    """Still images tiled in cells, `cols` per row: a real frame beside a keyframe, or a mapping of planned frames.
    Returns which image is in which cell; the picture itself carries no labels."""
    images = [Path(i) for i in images]
    if len(images) < 2: raise ValueError('sheet needs 2 or more images')
    for image in images:
        if not image.is_file(): raise ValueError(f'missing image {image}')
    if cols < 1: raise ValueError('cols must be 1 or more')
    if not (len(cell) == 2 and all(type(v) is int and v > 0 and v % 2 == 0 for v in cell)):
        raise ValueError('cell must be WxH with positive even numbers')
    w, h = cell
    output = fresh_output(output)
    with tempfile.TemporaryDirectory(prefix='video-sheet-') as temp:
        for i, image in enumerate(images):
            run(['ffmpeg', '-v', 'error', '-n', '-i', image, '-frames:v', '1',
                 '-vf', f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,format=rgb24',  # one pixel format, or the sequence drops cells
                 Path(temp) / f'{i:04d}.png'])
        run(['ffmpeg', '-v', 'error', '-n', '-i', Path(temp) / '%04d.png', '-frames:v', '1',
             '-vf', f'tile={cols}x{-(-len(images) // cols)}', output])
    return [{'row': i // cols + 1, 'col': i % cols + 1, 'path': str(image)} for i, image in enumerate(images)]


def merge_runs(candidates, gap=0.1):
    """A shaky shot scores as a run of candidates a frame or two apart: keep the strongest of each run."""
    runs = []
    for c in sorted(candidates, key=lambda c: c['t']):
        if runs and c['t'] - runs[-1][-1]['t'] <= gap + 1e-9: runs[-1].append(c)
        else: runs.append([c])
    # a merged entry keeps the stretch it stands for: a real cut can hide inside a shaky run
    return [dict(max(run, key=lambda c: c['score']), **({'from': run[0]['t'], 'to': run[-1]['t']} if len(run) > 1 else {})) for run in runs]


def parse_scene_scores(log):
    """(seconds, scene score) per frame that ffmpeg's metadata=print reported."""
    return [(float(t), float(s)) for t, s in re.findall(r'pts_time:([0-9.]+)[^\n]*\n[^\n]*lavfi\.scene_score=([0-9.]+)', log)]


def shots_from_cuts(cut_times, duration):
    bounds = [0] + sorted({t for t in cut_times if 0 < t < duration}) + [duration]
    return [{'id': f's{i + 1:02d}', 'start': a, 'end': b} for i, (a, b) in enumerate(zip(bounds, bounds[1:]))]


def cuts(source, output_dir, threshold=0.3, low=0.2):
    """Draft reference breakdown: detected cuts, start/mid/end frames and a clip per shot. Paths are kept as given,
    so run it from the project directory. Detection is a proposal: dissolves, flashes and whip pans need review.
    Scene changes scored between `low` and `threshold` are kept as `candidates` to be looked at, not cut on."""
    out = Path(output_dir)
    out.resolve().mkdir(parents=True, exist_ok=False)
    # ponytail: ffmpeg scene score only; swap in PySceneDetect if soft transitions dominate the references
    log = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(source), '-an', '-vf',
                          f"setpts=PTS-STARTPTS,select='gt(scene,{min(low, threshold)})',metadata=print", '-f', 'null', '-'],
                         capture_output=True, text=True, check=True).stderr
    video = next(s for s in probe(source)['streams'] if s['codec_type'] == 'video')
    num, den = video['r_frame_rate'].split('/')
    duration = video_duration(source)
    scores = [(t, s) for t, s in parse_scene_scores(log) if 0 < t < duration]
    shots = shots_from_cuts([t for t, s in scores if s > threshold], duration)
    for shot in shots:
        start, end, sid = shot['start'], shot['end'], shot['id']
        d = min(0.05, (end - start) / 4)  # stay inside the shot: an exact cut time can return the neighbour frame
        shot['stills'] = []
        for name, t in (('start', start + d), ('mid', (start + end) / 2), ('end', end - d)):
            still = out / f'{sid}-{name}.png'
            run(['ffmpeg', '-v', 'error', '-n', '-ss', f'{t:.3f}', '-i', source, '-frames:v', '1', still])
            shot['stills'].append(str(still))
        shot['clip'] = str(out / f'{sid}.mp4')
        run(['ffmpeg', '-v', 'error', '-n', '-ss', f'{start:.3f}', '-i', source, '-t', f'{end - start:.3f}', '-an',
             '-c:v', 'libx264', '-pix_fmt', 'yuv420p', shot['clip']])
        shot.update(camera='', camera_evidence=[], action='', events=[], plan={'source': '', 'what': '', 'caption': ''})
    draft = {'version': 1, 'source': {'path': str(source), 'sha256': hashlib.sha256(Path(source).read_bytes()).hexdigest(),
                                      'fps': int(num) / int(den), 'duration': duration, 'rights': ''},
             'match': '', 'setup': dict.fromkeys(('premise', 'tone', 'avoid', 'lead', 'setting'), ''),
             'candidates': merge_runs([{'t': round(t, 3), 'score': round(s, 3)} for t, s in scores if s <= threshold]), 'shots': shots}
    (out / 'reference-draft.json').write_text(json.dumps(draft, indent=2))
    return draft


DUP, MOVING = 0.6, 1.0  # mean abs luma difference to the previous frame: a repeat sits far below the motion around it


def repeated_frames(diffs):
    """Frames that repeat the one before while the picture is moving. diffs[i] = frame i against frame i-1.
    The last frame is skipped: there is no next frame to rebuild it from."""
    return [i for i in range(2, len(diffs) - 1) if diffs[i] < DUP and diffs[i - 1] > MOVING]


def frame_diffs(source):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(source), '-an', '-vf',
                          'tblend=all_mode=difference,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-',
                          '-f', 'null', '-'], capture_output=True, text=True, check=True).stdout
    return [0.0] + [float(v) for v in re.findall(r'YAVG=([0-9.]+)', out)]


def dupes(source, fix=None):
    """Find frames a web export repeated (often one per second); with `fix`, write a copy where each is replaced
    by the average of its neighbours. Returns {'frames', 'repeated'}."""
    if fix is not None: fix = fresh_output(fix)
    diffs = frame_diffs(source)
    result = {'frames': len(diffs), 'repeated': repeated_frames(diffs)}
    if fix is None or not result['repeated']:
        if fix is not None: run(['ffmpeg', '-v', 'error', '-n', '-i', source, '-an', '-c:v', 'copy', fix])
        return result
    video = next(s for s in probe(source)['streams'] if s['codec_type'] == 'video')
    width, height, size = video['width'], video['height'], video['width'] * video['height'] * 3 // 2
    raw = ['-f', 'rawvideo', '-pix_fmt', 'yuv420p']
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(source), *raw, '-'], stdout=subprocess.PIPE)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-n', *raw, '-s', f'{width}x{height}', '-r', video['r_frame_rate'], '-i', '-',
                            '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', str(fix)], stdin=subprocess.PIPE)
    # ponytail: a plain average ghosts for one frame on fast motion; use motion interpolation if that shows on review
    bad, prev, cur, i = set(result['repeated']), None, None, -1
    while True:
        nxt = dec.stdout.read(size)
        if cur is not None:
            if i in bad and len(nxt) == size: cur = bytes((a + b) >> 1 for a, b in zip(prev, nxt))
            enc.stdin.write(cur)
        if len(nxt) != size: break
        prev, cur, i = cur, nxt, i + 1
    enc.stdin.close(); dec.stdout.close()
    if dec.wait() or enc.wait(): raise RuntimeError('ffmpeg failed while rewriting frames; inspect the output')
    return result


def _percentile(values, q):
    values = sorted(values); k = (len(values) - 1) * q / 100; lo = int(k)
    return values[lo] + (values[min(lo + 1, len(values) - 1)] - values[lo]) * (k - lo)


def _crossings(series, fps):
    """(seconds, rising) where a series crosses the midpoint of its own range, and that range."""
    lo, hi = _percentile(series, 5), _percentile(series, 95); mid = (lo + hi) / 2
    return [((i + (mid - a) / (b - a)) / fps, b > a) for i, (a, b) in enumerate(zip(series, series[1:]))
            if (a - mid) * (b - mid) < 0], hi - lo


def spread_of(frames, fps):
    """How far apart the members of a group change state. frames: one row of cell brightness per frame, a cell being
    about one member. Each cell's crossing is compared with the whole picture's crossing for the same beat.
    spread_s is half the 10th-90th percentile width: 0.25 reads as 'each up to a quarter second early or late'."""
    cells = [[sum(col[max(0, i - 1):i + 2]) / len(col[max(0, i - 1):i + 2]) for i in range(len(col))] for col in zip(*frames)]
    beats, _ = _crossings([sum(row) / len(row) for row in zip(*cells)], fps)
    if not beats: raise ValueError('no state change found in this window')
    ranges = sorted(_crossings(c, fps)[1] for c in cells)
    floor = 0.4 * ranges[len(ranges) // 2]  # cells that barely change hold someone standing still or background
    offsets, used = [], 0
    for cell in cells:
        found, amount = _crossings(cell, fps)
        if amount <= floor: continue
        used += 1
        for t, rising in beats:
            near = [c - t for c, r in found if r == rising and abs(c - t) < 0.6]
            if near: offsets.append(min(near, key=abs))
    if not offsets: raise ValueError('no cell follows the beats in this window')
    p10, p90 = _percentile(offsets, 10), _percentile(offsets, 90)
    return {'beats': len(beats), 'cells': used, 'spread_s': round((p90 - p10) / 2, 3), 'p10_s': round(p10, 3), 'p90_s': round(p90, 3)}


def spread(source, start, end, grid, crop=None):
    """spread_of for a clip between two times; grid = (columns, rows) sized so one cell holds about one member.
    crop is an ffmpeg crop expression (w:h:x:y) for the part of the frame the group occupies."""
    columns, rows = grid
    video = next(s for s in probe(source)['streams'] if s['codec_type'] == 'video')
    num, den = video['r_frame_rate'].split('/')
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{start:.3f}', '-t', f'{end - start:.3f}', '-i', str(source), '-an', '-vf',
                          (f'crop={crop},' if crop else '') + f'scale={columns}:{rows}:flags=area,format=gray',
                          '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
    n = columns * rows
    return spread_of([list(raw[i:i + n]) for i in range(0, len(raw) - n + 1, n)], int(num) / int(den))


def parse_centres(text):
    centres = [tuple(float(v) for v in item.split(':')) for item in text.split(',')]
    if any(len(c) != 2 for c in centres) or any(b[0] <= a[0] for a, b in zip(centres, centres[1:])):
        raise ValueError('centres are t:x pairs with increasing t, e.g. 0:780,3.04:1178')
    return centres


def reframe_filter(centres, crop_width, size, source_size):
    """Crop a moving window out of a wider source and pad it to the target aspect, so a reference shot in another
    aspect ratio can sit beside the previs at the same scale. centres: [(seconds, x of the window centre)]."""
    (width, height), (source_width, source_height) = size, source_size
    if not centres: raise ValueError('at least one centre is required')
    if crop_width > source_width: raise ValueError('crop is wider than the source')
    padded = int(round(crop_width * height / width / 2)) * 2
    if padded < source_height: raise ValueError('target is wider than the crop; choose a wider crop')
    expr = f'{centres[-1][1]:g}'
    for (ta, a), (tb, b) in reversed(list(zip(centres, centres[1:]))):
        expr = f'if(lt(t\\,{tb:g})\\,{a:g}+({b:g}-{a:g})*(t-{ta:g})/{tb - ta:g}\\,{expr})'
    x = f'min(max({expr}-{crop_width / 2:g}\\,0)\\,{source_width - crop_width:g})'
    return f'crop={crop_width}:{source_height}:{x}:0,pad={crop_width}:{padded}:0:(oh-ih)/2,scale={width}:{height},setsar=1'


def reframe(source, output, size, crop_width, centres, fps):
    video = next(s for s in probe(source)['streams'] if s['codec_type'] == 'video')
    vf = reframe_filter(centres, crop_width, size, (video['width'], video['height']))
    run(['ffmpeg', '-v', 'error', '-n', '-i', source, '-an', '-vf', vf, '-r', str(fps), '-c:v', 'libx264', '-crf', '18',
         '-pix_fmt', 'yuv420p', fresh_output(output)])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    q = sub.add_parser('probe'); q.add_argument('input')
    q = sub.add_parser('extract'); q.add_argument('input'); q.add_argument('output_dir'); q.add_argument('--every', type=float, default=1)
    q = sub.add_parser('encode'); q.add_argument('sequence', help='PNG pattern, e.g. frame_%%04d.png'); q.add_argument('output'); q.add_argument('--fps', type=int, required=True)
    q = sub.add_parser('assemble'); q.add_argument('manifest'); q.add_argument('output')
    q = sub.add_parser('compare'); q.add_argument('left'); q.add_argument('right'); q.add_argument('output')
    q = sub.add_parser('pair', help='previs-over-take contact sheet'); q.add_argument('top'); q.add_argument('bottom')
    q.add_argument('output'); q.add_argument('--points', type=int, default=5)
    q.add_argument('--times', help='comma-separated seconds applied to both sources, e.g. 0.24,7.4; replaces --points')
    q = sub.add_parser('continuity', help='keyframes per role shared by 2+ shots'); q.add_argument('state'); q.add_argument('output')
    q = sub.add_parser('sheet', help='still images side by side'); q.add_argument('output'); q.add_argument('images', nargs='+')
    q.add_argument('--cols', type=int, default=2); q.add_argument('--cell', default='270x480', help='WxH of one cell, e.g. 540x960 for review')
    q = sub.add_parser('cuts', help='draft reference breakdown from detected cuts'); q.add_argument('input')
    q.add_argument('output_dir'); q.add_argument('--threshold', type=float, default=0.3)
    q.add_argument('--low', type=float, default=0.2, help='scene score above which a change is listed as a candidate cut')
    q = sub.add_parser('dupes', help='find frames repeated by an export; --fix writes a repaired copy'); q.add_argument('input'); q.add_argument('--fix')
    q = sub.add_parser('spread', help='how far apart the members of a group change state'); q.add_argument('input')
    q.add_argument('--start', type=float, required=True); q.add_argument('--end', type=float, required=True)
    q.add_argument('--grid', required=True, help='COLUMNSxROWS, about one group member per cell'); q.add_argument('--crop', help='w:h:x:y')
    q = sub.add_parser('reframe', help='crop a reference to the delivery aspect for comparison'); q.add_argument('input'); q.add_argument('output')
    q.add_argument('--size', required=True, help='WxH of the result'); q.add_argument('--crop-width', type=int, required=True)
    q.add_argument('--centres', required=True, help='t:x pairs, the window centre over time'); q.add_argument('--fps', type=int, required=True)
    a = p.parse_args()
    if a.action == 'probe': print(json.dumps(probe(a.input), indent=2))
    elif a.action == 'dupes':
        result = dupes(a.input, a.fix); print(json.dumps(result))
        if result['repeated'] and not a.fix: raise SystemExit(1)
    elif a.action == 'spread':
        print(json.dumps(spread(a.input, a.start, a.end, tuple(int(v) for v in a.grid.split('x')), a.crop)))
    elif a.action == 'reframe':
        reframe(a.input, a.output, tuple(int(v) for v in a.size.split('x')), a.crop_width, parse_centres(a.centres), a.fps)
    elif a.action == 'cuts': print(json.dumps(cuts(a.input, a.output_dir, a.threshold, a.low), indent=2))
    elif a.action == 'sheet':
        if not re.fullmatch(r'\d+x\d+', a.cell): raise ValueError('cell must be WxH with positive even numbers')
        print(json.dumps(sheet(a.images, a.output, a.cols, tuple(int(v) for v in a.cell.split('x'))), indent=2))
    elif a.action == 'continuity': print(json.dumps(continuity(a.state, a.output), indent=2))
    elif a.action == 'pair':
        pair(a.top, a.bottom, a.output, a.points, [float(t) for t in a.times.split(',')] if a.times else None)
    elif a.action == 'assemble': assemble(a.manifest, a.output)
    elif a.action == 'extract':
        if a.every <= 0: raise ValueError('--every must be positive')
        out = Path(a.output_dir).resolve(); out.mkdir(parents=True, exist_ok=False)
        run(['ffmpeg', '-v', 'error', '-n', '-i', a.input, '-vf', f'fps=1/{a.every}', out / 'frame_%06d.png'])
    elif a.action == 'encode':
        if a.fps <= 0: raise ValueError('fps must be positive')
        run(['ffmpeg', '-v', 'error', '-n', '-framerate', str(a.fps), '-start_number', '1', '-i', a.sequence,
             '-c:v', 'libx264', '-pix_fmt', 'yuv420p', fresh_output(a.output)])
    elif a.action == 'compare':
        run(['ffmpeg', '-v', 'error', '-n', '-i', a.left, '-i', a.right, '-filter_complex',
             '[0:v]setpts=PTS-STARTPTS,scale=360:640:force_original_aspect_ratio=decrease,pad=360:640:(ow-iw)/2:(oh-ih)/2,setsar=1[l];'
             '[1:v]setpts=PTS-STARTPTS,scale=360:640:force_original_aspect_ratio=decrease,pad=360:640:(ow-iw)/2:(oh-ih)/2,setsar=1[r];[l][r]hstack=shortest=1[v]',
             '-map', '[v]', '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', fresh_output(a.output)])

if __name__ == '__main__': main()
