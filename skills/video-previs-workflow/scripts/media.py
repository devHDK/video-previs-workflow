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


def parse_cut_times(log):
    return [float(t) for t in re.findall(r'pts_time:([0-9.]+)', log)]


def shots_from_cuts(cut_times, duration):
    bounds = [0] + sorted({t for t in cut_times if 0 < t < duration}) + [duration]
    return [{'id': f's{i + 1:02d}', 'start': a, 'end': b} for i, (a, b) in enumerate(zip(bounds, bounds[1:]))]


def cuts(source, output_dir, threshold=0.3):
    """Draft reference breakdown: detected cuts, start/mid/end frames and a clip per shot. Paths are kept as given,
    so run it from the project directory. Detection is a proposal: dissolves, flashes and whip pans need review."""
    out = Path(output_dir)
    out.resolve().mkdir(parents=True, exist_ok=False)
    # ponytail: ffmpeg scene score only; swap in PySceneDetect if soft transitions dominate the references
    log = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(source), '-an', '-vf',
                          f"setpts=PTS-STARTPTS,select='gt(scene,{threshold})',showinfo", '-f', 'null', '-'],
                         capture_output=True, text=True, check=True).stderr
    video = next(s for s in probe(source)['streams'] if s['codec_type'] == 'video')
    num, den = video['r_frame_rate'].split('/')
    duration = video_duration(source)
    shots = shots_from_cuts(parse_cut_times(log), duration)
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
        shot.update(camera='', camera_evidence=[], action='', events=[])
    draft = {'version': 1, 'source': {'path': str(source), 'sha256': hashlib.sha256(Path(source).read_bytes()).hexdigest(),
                                      'fps': int(num) / int(den), 'duration': duration},
             'setup': dict.fromkeys(('premise', 'tone', 'avoid', 'lead', 'setting'), ''), 'shots': shots}
    (out / 'reference-draft.json').write_text(json.dumps(draft, indent=2))
    return draft


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
    q = sub.add_parser('cuts', help='draft reference breakdown from detected cuts'); q.add_argument('input')
    q.add_argument('output_dir'); q.add_argument('--threshold', type=float, default=0.3)
    a = p.parse_args()
    if a.action == 'probe': print(json.dumps(probe(a.input), indent=2))
    elif a.action == 'cuts': print(json.dumps(cuts(a.input, a.output_dir, a.threshold), indent=2))
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
