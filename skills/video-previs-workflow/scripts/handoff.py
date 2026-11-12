"""Manual web generation: pack a job's inputs for a person to upload, then ingest the one result they drop back.
Never edits project state and never drives a provider's web app."""
import hashlib
import re
import shutil
from pathlib import Path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def slug(text):
    return re.sub(r'\W+', '-', str(text).lower()).strip('-') or 'input'


def pack(job, root, out_dir):
    """Copy inputs to OUT_DIR/NN-<slot>.<ext>, write request.md and an empty output/. Validates before writing."""
    root, out_dir = Path(root), Path(out_dir)
    inputs = job.get('inputs') if isinstance(job, dict) else None
    if not (isinstance(inputs, list) and inputs and job.get('model') and job.get('prompt')):
        raise ValueError('job: model, prompt and inputs are required')
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
             '| file | slot | purpose |', '|---|---|---|', *rows, '', '## Prompt', '', '```text', job['prompt'], '```', '',
             '## Result', '', f"Expected: {output.get('kind', 'file')}. {output.get('notes', '')}".rstrip(),
             '', 'Put exactly one result file in `output/`.', '']
    (out_dir / 'request.md').write_text('\n'.join(lines))
    (out_dir / 'output').mkdir()
    return records
