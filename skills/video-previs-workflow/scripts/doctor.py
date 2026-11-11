"""Report local runtime availability; does not install anything or inspect credentials."""
import json
import shutil
import sys
from pathlib import Path

def main():
    found = {name: shutil.which(name) for name in ('blender', 'ffmpeg', 'ffprobe')}
    mac = Path('/Applications/Blender.app/Contents/MacOS/Blender')
    if not found['blender'] and mac.is_file(): found['blender'] = str(mac)
    print(json.dumps({'python': sys.version.split()[0], 'tools': found,
                      'generation_tools': 'Discover MCP and authentication separately in this host.'}, indent=2))
    return 0 if all(found.values()) else 1

if __name__ == '__main__': raise SystemExit(main())
