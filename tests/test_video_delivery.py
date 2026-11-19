import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/video-previs-workflow/scripts"
sys.path.insert(0, str(SCRIPTS))
import gate
import handoff
import state


class DeliveryTests(unittest.TestCase):
    def test_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("p.mp4", "a.png", "b.png"):
                (root / name).touch()
            inputs = [
                dict(path="p.mp4", tag="@Video1", slot="video"),
                dict(path="a.png", shot="a", tag="@Image1", slot="image"),
                dict(path="b.png", shot="b", tag="@Image2", slot="image"),
            ]
            job = dict(
                model="demo",
                generation_mode="multi_cut",
                shot="a",
                shots=["a", "b"],
                route="manual",
                duration_s=4,
                inputs=inputs,
                prompt="Follow @Video1.",
                beats=[
                    dict(shot="a", start_s=0, action="sit"),
                    dict(shot="b", start_s=2, action="stand"),
                ],
            )
            handoff.pack(job, root, root / "ok")
            doc = (root / "ok/request.md").read_text()
            self.assertIn("2–4 s @Image2", doc)
            self.assertIn("- duration: 4 s", doc)
            inputs[2]["tag"] = "@Image1"
            with self.assertRaises(ValueError):
                handoff.pack(job, root, root / "bad")
            self.assertFalse((root / "bad").exists())

    def test_format_guidance(self):
        doc = (SCRIPTS.parent / "references/production.md").read_text()
        self.assertIn("For `match: format`, design", doc)
        self.assertNotIn("one shot, and on the reference-led route", doc)

    def test_duration(self):
        from generation_job import validate_job

        with self.assertRaisesRegex(ValueError, "duration"):
            validate_job(
                dict(generation_mode="one_take", shot="a", duration_s=16),
                dict(max_duration_s=15),
            )

    def test_delivery_mismatch(self):
        from delivery_check import delivery_errors

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "v.mp4").touch()
            cfg = dict(
                output=dict(total_frames=708, width=10, height=10, fps=24), shots=[]
            )
            manifest = dict(clips=[dict(frames=709, shot="x", path="v.mp4")])
            cfg["shots"] = [dict(id="x", selected_output="v.mp4")]
            stream = dict(
                codec_type="video",
                nb_read_frames="709",
                width=10,
                height=10,
                avg_frame_rate="24/1",
            )
            with patch("delivery_check.probe", return_value=dict(streams=[stream])):
                self.assertIn(
                    "708", str(delivery_errors(cfg, root, manifest, root / "v.mp4"))
                )
                cfg["output"]["total_frames"] = 709
                self.assertEqual(
                    delivery_errors(cfg, root, manifest, root / "v.mp4"), []
                )
                cfg["shots"] = [dict(id="x", required_events=["sit"])]
                self.assertTrue(delivery_errors(cfg, root, manifest, root / "v.mp4"))

    def test_selection_batch(self):
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for f in ("original", "a", "b"):
                (root / f).write_bytes(f.encode())
            sha = hashlib.sha256(b"original").hexdigest()
            project = dict(
                shots=[dict(id=s, frames=4, required_events=["sit"]) for s in "ab"],
                jobs=[
                    dict(
                        request_id="j",
                        shots=["a", "b"],
                        status="succeeded",
                        outputs=[dict(path="original", sha256=sha)],
                    )
                ],
            )
            path = root / "state.json"
            path.write_text(json.dumps(project))
            rows = [
                dict(
                    shot=s,
                    source="original",
                    request_id="j",
                    start=i * 4,
                    end=i * 4 + 4,
                    take=s,
                    target_frames=4,
                    hold_frames=0,
                )
                for i, s in enumerate("ab")
            ]
            with patch(
                "delivery_check.video_info",
                side_effect=lambda p: dict(
                    frames=8 if p.name == "original" else 4, fps=24, width=1, height=1
                ),
            ):
                rows[-1]["end"] = 9
                with self.assertRaises(ValueError):
                    state.select_takes(path, rows)
                self.assertEqual(json.loads(path.read_text()), project)
                rows[-1].update(end=7, hold_frames=1, hold_acceptance=False)
                with self.assertRaises(ValueError):
                    state.select_takes(path, rows)
                rows[-1].update(end=8, hold_frames=0)
                state.select_takes(path, rows)
                before = path.read_bytes()
                state.select_takes(path, rows)
                self.assertEqual(before, path.read_bytes())
                self.assertTrue(gate.check_qa(json.loads(before), root))

    def test_mode_cardinality_and_one_take_direction(self):
        from generation_job import validate_job, prompt_text

        legacy = dict(prompt="Locked camera.")
        validate_job(legacy)
        self.assertEqual(prompt_text(legacy), legacy["prompt"])
        job = dict(
            legacy, shot="a", shots=["a", "b"], duration_s=5, generation_mode="per_shot"
        )
        with self.assertRaises(ValueError):
            validate_job(job)
        job["generation_mode"] = "one_take"
        validate_job(job)
        self.assertIn("no internal cuts", prompt_text(job))

    def test_deliver_cli_state_and_manifest_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "state.json"
            shots = [dict(id=s, selected_output=s) for s in ("a", "b")]
            for s in shots:
                (root / s["id"]).touch()
            path.write_text(
                json.dumps(
                    dict(
                        shots=shots,
                        output=dict(total_frames=2, width=10, height=10, fps=24),
                    )
                )
            )
            mp4 = root / "v.mp4"
            mp4.touch()
            manifest = root / "edit.json"
            clips = [dict(shot=s["id"], frames=1, path=s["id"]) for s in shots]
            with patch(
                "delivery_check.video_info",
                return_value=dict(width=10, height=10, fps=24, frames=2),
            ):
                manifest.write_text(json.dumps(dict(clips=clips[::-1])))
                with self.assertRaisesRegex(ValueError, "order"):
                    state.deliver(path, manifest, mp4)
                manifest.write_text(json.dumps(dict(clips=clips)))
                state.deliver(path, manifest, mp4)
                self.assertEqual(json.loads(path.read_text())["stage"], "delivered")
                before = path.read_bytes()
                state.deliver(path, manifest, mp4)
                self.assertEqual(before, path.read_bytes())
