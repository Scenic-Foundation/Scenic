"""Command-line tool converting folders of USD assets to GLTF meshes.

Run inside an Isaac Sim Python environment; see ``--help``.
"""

import argparse

from scenic.simulators.isaac.usd_conversion import assetConvert

if __name__ == "__main__":
    from scenic.simulators.isaac.backends import getBackend

    backend = getBackend("core_51")
    kit = backend.getSimulationApp()
    backend.enableExtension("omni.kit.asset_converter")

    parser = argparse.ArgumentParser(
        "Convert folders of USD assets to compressed glTF meshes (NAME_usd.glb.bz2)"
    )
    parser.add_argument(
        "--folders",
        type=str,
        nargs="+",
        default=None,
        help="List of folders (local paths or URLs, e.g. under the Isaac asset root) to convert.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Directory for the converted meshes (default: a _converted subfolder of each input folder).",
    )
    parser.add_argument(
        "--max-models",
        type=int,
        default=50,
        help="If specified, convert up to `max-models` per folder.",
    )
    parser.add_argument(
        "--load-materials",
        action="store_true",
        help="Keep materials/textures (not needed by Scenic; makes meshes much larger).",
    )
    parser.add_argument(
        "--environments",
        type=str,
        nargs="+",
        default=[],
        help="List of .usd filenames (not paths) to treat as environments.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing converted meshes instead of skipping them.",
    )

    args, unknown_args = parser.parse_known_args()
    if args.folders is not None:
        assetConvert(args, backend)
    else:
        print("No folders specified via --folders argument, exiting")

    backend.closeSimulationApp(kit)
