"""Validate explicit generation modes and render shot-tagged instructions."""
import math
import re
from pathlib import Path


def seconds(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_job(job, profile=None):
    mode = job.get("generation_mode")
    if mode is None:
        return
    ids = job.get("shots", [job.get("shot")])
    if mode not in ("per_shot", "multi_cut", "one_take"):
        raise ValueError("unknown generation_mode")
    if (
        not isinstance(ids, list)
        or not ids
        or not all(isinstance(s, str) and s for s in ids)
    ):
        raise ValueError("shot IDs required")
    if ids[0] != job.get("shot") or len(set(ids)) != len(ids):
        raise ValueError("shots must be distinct and begin with shot")
    if (mode == "per_shot" and len(ids) != 1) or (mode == "multi_cut" and len(ids) < 2):
        raise ValueError("shot count incompatible with mode")
    duration = job.get("duration_s")
    if not seconds(duration) or duration <= 0:
        raise ValueError("positive duration_s required")
    if profile and duration > profile["max_duration_s"]:
        raise ValueError("requested duration exceeds profile")
    if mode != "multi_cut" or job.get("route") != "manual":
        return
    inputs = job.get("inputs")
    if (
        not isinstance(inputs, list)
        or len(inputs) != len(ids) + 1
        or not all(isinstance(i, dict) for i in inputs)
    ):
        raise ValueError("expected one previs and one photo per shot")
    if profile and (
        profile.get("video_refs", 0) < 1 or profile.get("image_refs", 0) < len(ids)
    ):
        raise ValueError("reference count exceeds profile")
    tags = [i.get("tag") for i in inputs]
    if not all(isinstance(t, str) and re.fullmatch(r"@[\w-]+", t) for t in tags) or len(
        set(tags)
    ) != len(tags):
        raise ValueError("each reference needs a distinct @tag")
    if Path(inputs[0].get("path", "")).suffix.lower() not in (".mp4", ".mov"):
        raise ValueError("first input must be previs video")
    for sid, item in zip(ids, inputs[1:]):
        if item.get("shot") != sid or Path(item.get("path", "")).suffix.lower() not in (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        ):
            raise ValueError(f"{sid}: expected matching shot photo")
    beats = job.get("beats")
    if (
        not isinstance(beats, list)
        or not all(isinstance(b, dict) for b in beats)
        or [b.get("shot") for b in beats] != ids
    ):
        raise ValueError("timed beats must match shot order")
    starts = [b.get("start_s") for b in beats]
    if (
        not all(seconds(t) for t in starts)
        or starts[0] != 0
        or any(a >= b for a, b in zip(starts, starts[1:] + [duration]))
    ):
        raise ValueError("invalid beat times")
    for b in beats:
        if (
            not isinstance(b.get("action"), str)
            or not b["action"].strip()
            or "@" in b["action"]
        ):
            raise ValueError(
                "beat needs action text; photo tags are inserted automatically"
            )
    if set(re.findall(r"@[\w-]+", job.get("prompt", ""))) != {tags[0]}:
        raise ValueError("base prompt must reference only the previs tag")


def prompt_text(job):
    prompt = job["prompt"]
    if job.get("generation_mode") == "one_take":
        return (
            prompt
            + "\nKeep one continuous shot with uninterrupted action and no internal cuts."
        )
    if job.get("generation_mode") == "multi_cut" and job.get("route") == "manual":
        beats = job["beats"]
        ends = [b["start_s"] for b in beats[1:]] + [job["duration_s"]]
        lines = [
            f"{b['start_s']:g}–{end:g} s {item['tag']}: {b['action']}"
            for b, end, item in zip(beats, ends, job["inputs"][1:])
        ]
        return "\n".join([prompt, "Use hard cuts at the specified times.", *lines])
    return prompt
