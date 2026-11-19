"""Read-only frame measurements shared by selection and delivery commands."""
from fractions import Fraction
from pathlib import Path
import json
import hashlib
from media import probe


def video_info(path):
    stream = next(
        (s for s in probe(path)["streams"] if s.get("codec_type") == "video"), None
    )
    if not stream:
        raise ValueError(f"{path}: no video")
    return dict(
        frames=int(stream["nb_read_frames"]),
        fps=Fraction(stream["avg_frame_rate"]),
        width=stream["width"],
        height=stream["height"],
    )


def delivery_errors(state, root, manifest, mp4, manifest_dir=None):
    from gate import check_qa

    errors = check_qa(state, root)
    clips = manifest.get("clips", [])
    if not clips or any(
        not isinstance(c, dict) or type(c.get("frames")) is not int or c["frames"] <= 0
        for c in clips
    ):
        return errors + ["manifest needs positive clip frame counts"]
    manifest_dir = Path(manifest_dir or root)
    selected = {s["id"]: s.get("selected_output") for s in state.get("shots", [])}
    actual_ids = [c.get("shot") for c in clips]
    ref = state.get("reference", {}).get("path")
    if ref and (root / ref).is_file():
        expected = [s["id"] for s in json.loads((root / ref).read_text())["shots"]]
        if actual_ids != expected:
            errors.append("manifest shot order differs from reference timeline")
    elif [sid for sid in actual_ids if sid in selected] != list(selected):
        errors.append("manifest must include selected shots in timeline order")
    for clip in clips:
        path = clip.get("path")
        if not isinstance(path, str) or not (manifest_dir / path).is_file():
            errors.append(f"manifest clip source missing: {clip.get('shot')}")
            continue
        selection = selected.get(clip.get("shot"))
        if not selection:
            continue
        record = selection if isinstance(selection, dict) else {"take": selection}
        file = (manifest_dir / path).resolve()
        if not record.get("take") or file != (root / record["take"]).resolve():
            errors.append(f"manifest clip differs from selection: {clip.get('shot')}")
        elif (
            record.get("sha256")
            and hashlib.sha256(file.read_bytes()).hexdigest() != record["sha256"]
        ):
            errors.append(f"selected take changed: {path}")
        if "target_frames" in record and (
            clip["frames"] != record["target_frames"]
            or clip.get("start", 0)
            or clip.get("speed", 1) != 1
        ):
            errors.append(f"manifest changes reviewed edit: {clip.get('shot')}")
    stream = video_info(Path(mp4))
    output = state.get("output", {})
    target, total = output.get("total_frames"), sum(c["frames"] for c in clips)
    if target != total or total != stream["frames"]:
        errors.append(
            f"frames: target={target} manifest={total} encoded={stream['frames']}"
        )
    for key in ("width", "height", "fps"):
        if str(output.get(key)) != str(stream[key]) and output.get(key) != stream[key]:
            errors.append(f"{key}: target={output.get(key)} encoded={stream[key]}")
    return errors
