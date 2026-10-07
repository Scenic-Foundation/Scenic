import sdformat14 as sdf
import sys
import xml.etree.ElementTree as ET

from trimesh import load_mesh
from trimesh.transformations import compose_matrix
from trimesh.primitives import Box, Capsule, Cylinder, Sphere
from trimesh.creation import cone
from trimesh.boolean import union
from pathlib import Path
from scenic.core.utils import repairMesh

# to use sdformat python bindings:
# sudo apt install libsdformat14-dev python3-sdformat14
# add include-system-site-packages = true to your venv config file

def parse_sdf(input_file):
    """
    Returns a single combined mesh of all objects in the SDF file
    """
    root = sdf.Root()
    unifiedMeshes = []
    try:
        root.load(input_file)
    except sdf.SDFErrorsException as e:
        print(e, file=sys.stderr)
    world = root.world_by_index(0) # assume only one world
    
    # there's no way to get <include> tags under world
    # the methods to get them just don't exist in the Python bindings(but they do in the C++ API)
    # so it has to be done through parsing the xml
    
    # get <include> meshes under the <world> level
    unifiedMeshes += extractIncludeMeshes(input_file)
             
    # get <model> meshes from unifying collision geometries of the model's links
    for model_index in range(world.model_count()):
        sdfModel = world.model_by_index(model_index)
        newMesh = unifyModelMeshes(sdfModel)
        if newMesh:
            unifiedMeshes.append(newMesh)

    finalMesh = union(unifiedMeshes, engine='manifold')
    
    # Bottom of the mesh needs to be aligned with z=0 in the scenario file:
    # spawnHeight = bounds[1][2] / 2
    # setting = new SDFObject at (0, 0, spawnHeight)
    return finalMesh, finalMesh.bounds

def parse_sdf_for_graph(input_file):
    """
    Returns individual meshes of all objects in the SDF file
    """
    root = sdf.Root()
    unifiedMeshes = []
    try:
        root.load(input_file)
    except sdf.SDFErrorsException as e:
        print(e, file=sys.stderr)
    world = root.world_by_index(0) # assume only one world
    
    # there's no way to get <include> tags under world
    # the methods to get them just don't exist in the Python bindings(but they do in the C++ API)
    # so it has to be done through parsing the xml
    
    # get <include> meshes under the <world> level
    unifiedMeshes += extractIncludeMeshes(input_file)
             
    # get <model> meshes from unifying collision geometries of the model's links
    for model_index in range(world.model_count()):
        sdfModel = world.model_by_index(model_index)
        newMesh = unifyModelMeshes(sdfModel)
        if newMesh:
            unifiedMeshes.append(newMesh)

    return unifiedMeshes

def unifyModelMeshes(sdfModel, meshVersionDir=None):
    """
    Unifies the meshes of the links of the provided model into a single mesh
    """
    
    modelPose = sdfModel.raw_pose()
    meshes = []

    for link_index in range(sdfModel.link_count()):
        link = sdfModel.link_by_index(link_index)
        linkPose = link.raw_pose()
        linkTransform = compose_matrix(
            angles=[linkPose.roll(), linkPose.pitch(), linkPose.yaw()], 
            translate=[linkPose.x(), linkPose.y(), linkPose.z()]
        )

        for collision_index in range(link.collision_count()):
            collision = link.collision_by_index(collision_index)
            collisionPose = collision.raw_pose()
            collisionTransform = compose_matrix(
                angles=[collisionPose.roll(), collisionPose.pitch(), collisionPose.yaw()],
                translate=[collisionPose.x(), collisionPose.y(), collisionPose.z()]
            )
            geometry = collision.geometry()
            mesh = None
                  
            if geometry.type() == sdf.GeometryType.BOX:
                boxGeometry = geometry.box_shape().size()
                mesh = Box([boxGeometry.x(), boxGeometry.y(), boxGeometry.z()], linkTransform)
                    
            elif geometry.type() == sdf.GeometryType.CYLINDER:
                cylinderGeometry = geometry.cylinder_shape()
                mesh = Cylinder(cylinderGeometry.radius(), cylinderGeometry.length(), linkTransform)
                    
            elif geometry.type() == sdf.GeometryType.SPHERE:
                sphereGeometry = geometry.sphere_shape()
                mesh = Sphere(sphereGeometry.radius(), transform=linkTransform)
                    
            elif geometry.type() == sdf.GeometryType.CAPSULE:
                capsuleGeometry = geometry.capsule_shape()
                mesh = Capsule(capsuleGeometry.radius(), capsuleGeometry.length(), linkTransform)
                    
            elif geometry.type() == sdf.GeometryType.CONE:
                coneGeometry = geometry.cone_shape()
                mesh = cone(coneGeometry.radius(), coneGeometry.length(), transform=linkTransform)
                    
            elif geometry.type() == sdf.GeometryType.MESH:
                uri = geometry.mesh_shape().uri()
                scale = geometry.mesh_shape().scale()
                uriSplit = uri.split('/')
                
                if uriSplit[0] == 'https:':
                    meshPath = meshVersionDir / 'meshes' / uriSplit[10]
                    mesh = load_mesh(meshPath)
                    mesh = repairMesh(mesh)
                    mesh.apply_scale(scale[0])
                elif uriSplit[0] == 'meshes':
                    meshPath = meshVersionDir / 'meshes' / uriSplit[1]
                    mesh = load_mesh(meshPath)
                    mesh = repairMesh(mesh)
                    mesh.apply_scale(scale[0])
            else:
                print("Unsupported geometry") # plane, ellipsoid, polyline, heightmap
                
            if mesh:
                # place the collision element relative to others in the link
                mesh.apply_transform(collisionTransform)
                meshes.append(mesh)
                    
    if len(meshes) > 0:
        fullMesh = union(meshes, engine='manifold')
        modelTransform = compose_matrix(translate=[modelPose.x(), modelPose.y(), modelPose.z()])
        
        # place the model relative to the world and other models
        fullMesh.apply_transform(modelTransform)
        return fullMesh
    else:
        return None

def extractIncludeMeshes(input_file):
    """
    Returns a list of meshes from the <include> statements in the provided SDF
    """
    
    # find path to fuel model directory in filesystem
    tree = ET.parse(input_file)
    xmlroot = tree.getroot()
    includeMeshes = []
    
    for include in xmlroot.findall(".//include"):
        uri = include.findtext("uri", default="").strip()
        name = include.findtext("name", default="").strip()
        pose = include.findtext("pose", default="").strip()
        uriSplit = uri.split('/')
        poseSplit = pose.split(' ')
        model_dir_name = uriSplit[6].rstrip().rstrip('\n').lower()
        modelroot = (
            Path.home()
            / ".gz"
            / "fuel"
            / uriSplit[2]
            / uriSplit[4].lower()
            / "models"
            / model_dir_name
        )

        version_dir = max(
            (p for p in modelroot.iterdir() if p.is_dir() and p.name.isdigit()),
            key=lambda p: int(p.name)
        )

        modelSDF = version_dir / 'model.sdf'
        root = sdf.Root()
        try:
            root.load(str(modelSDF))
        except sdf.SDFErrorsException as e:
            print(e, file=sys.stderr)
            
        newMesh = unifyModelMeshes(root.model(), version_dir)
        if newMesh:
            includeMeshTransform = compose_matrix(
                angles=[float(poseSplit[3]), float(poseSplit[4]), float(poseSplit[5])],
                translate=[float(poseSplit[0]), float(poseSplit[1]), float(poseSplit[2])]
            )
            newMesh.apply_transform(includeMeshTransform)
            includeMeshes.append(newMesh)
        else:
            print("Failed to get <include> mesh!")
            
    return includeMeshes
