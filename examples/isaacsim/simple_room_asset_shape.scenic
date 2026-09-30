"""Place a USD asset on an existing table using the asset's own geometry as its shape.

The bin is spawned from the Isaac asset library, but Scenic needs a mesh to
reason about placement and collisions. That mesh is produced once from the
USD with the conversion tool (see "Converting USD assets to meshes" in the
README), run in an Isaac Sim Python environment:

    python src/scenic/simulators/isaac/usd_to_mesh.py \\
        --folders <isaac-assets>/Isaac/Props/KLT_Bin \\
        --output examples/isaacsim/assets/klt_bin

which writes the compressed mesh ``assets/klt_bin/small_KLT_usd.glb.bz2``.
"""

param environmentUSDPath = "Isaac/Environments/Simple_Room/simple_room.usd"

from lib import *
model scenic.simulators.isaac.model
from scenic.simulators.isaac.utils import getExistingObj, loadAssetMesh

table = getExistingObj("/Root/table_low_327/table_low")

class KltBin(IsaacSimObject):
    shape: MeshShape(loadAssetMesh(localPath("assets/klt_bin/small_KLT_usd.glb.bz2")))
    width: 0.2
    length: 0.3
    height: 0.15
    isaacAssetPath: "Isaac/Props/KLT_Bin/small_KLT.usd"
    physics: False

bin = new KltBin on table

toy = new Toy on table, right of bin by 0.3,
    with physics False
