"""FFmpeg helpers. Commands use argument arrays, preserve inputs, and reject output overwrites."""
import argparse
import json
from pathlib import Path
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


def clip_command(source, output, frames, fps, width, height):
    return ['ffmpeg', '-v', 'error', '-n', '-i', str(source), '-an', '-vf',
        f'fps={fps},scale={width}:{height}:force_original_aspect_ratio=decrease,'
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
    # Audio must already be mixed to the approved timeline. Clip audio is intentionally discarded.
    for key in ('audio', 'subtitles'):
        if data.get(key) and not resolve(data[key]).is_file(): raise FileNotFoundError(data[key])
    output = fresh_output(output)
    total = sum(c['frames'] for c in data['clips'])
    with tempfile.TemporaryDirectory(prefix='video-edit-') as temp:
        root = Path(temp)
        for i, clip in enumerate(data['clips']):
            run(clip_command(resolve(clip['path']), root / f'{i}.mp4', clip['frames'], data['fps'], data['width'], data['height']))
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    q = sub.add_parser('probe'); q.add_argument('input')
    q = sub.add_parser('extract'); q.add_argument('input'); q.add_argument('output_dir'); q.add_argument('--every', type=float, default=1)
    q = sub.add_parser('encode'); q.add_argument('sequence', help='PNG pattern, e.g. frame_%04d.png'); q.add_argument('output'); q.add_argument('--fps', type=int, required=True)
    q = sub.add_parser('assemble'); q.add_argument('manifest'); q.add_argument('output')
    q = sub.add_parser('compare'); q.add_argument('left'); q.add_argument('right'); q.add_argument('output')
    a = p.parse_args()
    if a.action == 'probe': print(json.dumps(probe(a.input), indent=2))
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
