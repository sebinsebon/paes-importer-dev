"""Copy the explicitly selected consumer's shared runtime; never discover a target."""
import argparse
from pathlib import Path
import shutil

from dev_paths import RUNTIME_ROOT as ROOT, DEV_ROOT, WORK_ROOT

def sync(target, replace=False):
    target = Path(target).resolve(strict=True)
    if not (target / "package.json").is_file():
        raise ValueError("Target must be a web project containing package.json")
    pairs = [(ROOT / "viewer" / name, target / "lib/paessed-runtime" / name)
             for name in ("validator.js", "package-reader.js", "block-renderer.js")]
    pairs.append((ROOT / "viewer/vendor/katex/dist/katex.min.js", target / "lib/paessed-runtime/katex.js"))
    pairs.append((ROOT / "viewer/block-renderer.css", target / "public/paessed/block-renderer.css"))
    dist = ROOT / "viewer/vendor/katex/dist"
    pairs += [(path, target / "public/paessed/katex" / path.relative_to(dist))
              for path in dist.rglob("*") if path.is_file() and path.suffix in (".css", ".woff", ".woff2", ".ttf")]
    pairs.append((ROOT / "viewer/vendor/katex/LICENSE", target / "public/paessed/katex/LICENSE"))
    # Check the entire operation before changing any file. Resolve every destination
    # so a junction/symlink cannot redirect writes outside the selected target.
    for source, destination in pairs:
        destination.resolve().relative_to(target)
        if not source.is_file():
            raise ValueError(f"Missing runtime source: {source}")
        if destination.exists() and source.read_bytes() != destination.read_bytes() and not replace:
            raise ValueError(f"Different existing file; use --replace explicitly: {destination}")
    for source, destination in pairs:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return len(pairs)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    print(f"Synced {sync(args.target, args.replace)} licensed runtime files")
