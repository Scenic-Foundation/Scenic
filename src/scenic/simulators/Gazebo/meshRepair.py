import sys

import trimesh

from scenic.core.utils import repairMesh

"""
argv[1] is the name of the file to be changed
argv[2] is the name of the new repaired mesh to be generated

file type conversion is handled automatically handled by trimesh
by inference from file names
"""

if __name__ == "__main__":
    file_name = sys.argv[1]
    new_file_name = sys.argv[2]
    mesh = trimesh.load(file_name)
    mesh = repairMesh(mesh)
    mesh.export(new_file_name)
