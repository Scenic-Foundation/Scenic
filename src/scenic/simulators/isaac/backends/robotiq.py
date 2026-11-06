"""USD authoring for the Robotiq 2F-85 gripper (``gripperStyle == "robotiq_2f85"``).

The stock Isaac UR5e asset ships the gripper without a working closed-loop
linkage or usable drives, so before the articulation is created the backends
patch the USD stage: attach the gripper, set the home pose, author the passive
inner-knuckle joints, and configure the finger drives. These operations only
use ``pxr``/PhysX schemas, so they are shared by every backend.
"""

import numpy as np


def requireStagePrim(stage, prim_path):
    """Return the prim at ``prim_path``, raising if the stage or prim is missing."""
    if stage is None:
        raise RuntimeError("Required Isaac USD stage is missing")
    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid():
        raise RuntimeError(f"Required Isaac prim is missing: {prim_path}")
    return prim


def _setAttr(prim, attr_name, value, value_type):
    attr = prim.GetAttribute(attr_name)
    if not attr or not attr.IsValid():
        attr = prim.CreateAttribute(attr_name, value_type)
    attr.Set(value)
    return attr


def _setFloatAttrs(prim, values):
    from pxr import Sdf

    for attr_name, value in values:
        _setAttr(prim, attr_name, float(value), Sdf.ValueTypeNames.Float)


def _definePhysicsMaterial(stage, path, static_friction, dynamic_friction):
    from pxr import PhysxSchema, UsdPhysics, UsdShade

    material_prim = UsdShade.Material.Define(stage, path).GetPrim()
    material_api = UsdPhysics.MaterialAPI.Apply(material_prim)
    material_api.CreateStaticFrictionAttr().Set(float(static_friction))
    material_api.CreateDynamicFrictionAttr().Set(float(dynamic_friction))
    material_api.CreateRestitutionAttr().Set(0.0)

    physx_material_api = PhysxSchema.PhysxMaterialAPI.Apply(material_prim)
    physx_material_api.CreateFrictionCombineModeAttr().Set("max")
    physx_material_api.CreateRestitutionCombineModeAttr().Set("min")


def _collisionPrims(root):
    from pxr import Usd

    return [
        prim
        for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies())
        if any("Collision" in schema for schema in prim.GetAppliedSchemas())
    ]


def configureRobotiqGripper(stage, prim_path, profile):
    """Author the gripper attachment, home pose, closed-loop linkage, and drives."""
    _configureAttachment(stage, prim_path)
    _configureDefaultJointPose(stage, prim_path, profile)
    _configureClosedLoop(stage, prim_path, profile)
    _configureDrives(stage, prim_path, profile)


def _configureAttachment(stage, prim_path):
    from pxr import Gf, Sdf

    joint = requireStagePrim(stage, f"{prim_path}/joints/robot_gripper_joint")
    for attr_name, (w, x, y, z) in (
        ("physics:localRot0", (0.70710677, 0.0, 0.0, 0.70710677)),
        ("physics:localRot1", (1.0, 0.0, 0.0, 0.0)),
    ):
        quat = Gf.Quatf(float(w), Gf.Vec3f(float(x), float(y), float(z)))
        _setAttr(joint, attr_name, quat, Sdf.ValueTypeNames.Quatf)


def _configureDefaultJointPose(stage, prim_path, profile):
    pose_attrs = (
        "drive:angular:physics:targetPosition",
        "state:angular:physics:position",
    )

    for joint_name, angle_deg in zip(
        profile.armDofNames, np.rad2deg(profile.defaultArmPose)
    ):
        joint = requireStagePrim(stage, f"{prim_path}/joints/{joint_name}")
        _setFloatAttrs(joint, [(name, angle_deg) for name in pose_attrs])

    gripper_joint = requireStagePrim(
        stage, f"{prim_path}/{profile.gripperPrim}/Joints/finger_joint"
    )
    _setFloatAttrs(
        gripper_joint, [(name, profile.openGripperPositions[0]) for name in pose_attrs]
    )


def _configureDrives(stage, prim_path, profile):
    from pxr import PhysxSchema, Sdf, Usd, UsdPhysics

    gripper_root = requireStagePrim(stage, f"{prim_path}/{profile.gripperPrim}")
    found_finger_joint = False

    def setDriveAttrs(prim, max_force, stiffness, damping, target_velocity=0.0):
        if "PhysicsDriveAPI:angular" not in list(prim.GetAppliedSchemas()):
            UsdPhysics.DriveAPI.Apply(prim, "angular")
        _setFloatAttrs(
            prim,
            (
                ("drive:angular:physics:maxForce", max_force),
                ("drive:angular:physics:stiffness", stiffness),
                ("drive:angular:physics:damping", damping),
                ("drive:angular:physics:targetVelocity", target_velocity),
            ),
        )
        _setAttr(prim, "drive:angular:physics:type", "force", Sdf.ValueTypeNames.Token)
        joint_api = (
            PhysxSchema.PhysxJointAPI(prim)
            if prim.HasAPI(PhysxSchema.PhysxJointAPI)
            else PhysxSchema.PhysxJointAPI.Apply(prim)
        )
        joint_api.CreateMaxJointVelocityAttr().Set(
            float(profile.gripperMaxJointVelocityDegPerSec)
        )

    for prim in Usd.PrimRange(gripper_root):
        name = prim.GetName()
        if "Joint" not in str(prim.GetTypeName()) and not name.endswith("_joint"):
            continue
        for schema in list(prim.GetAppliedSchemas()):
            if not schema.startswith("PhysxMimicJointAPI:"):
                continue
            axis = schema.split(":", 1)[1]
            _setFloatAttrs(
                prim,
                (
                    (
                        f"physxMimicJoint:{axis}:naturalFrequency",
                        profile.mimicNaturalFrequency,
                    ),
                    (f"physxMimicJoint:{axis}:dampingRatio", profile.mimicDampingRatio),
                ),
            )
        if name == "finger_joint":
            found_finger_joint = True
            setDriveAttrs(
                prim,
                profile.gripperMaxForce,
                profile.gripperStiffness,
                profile.gripperDamping,
            )
            _setFloatAttrs(
                prim,
                (
                    ("physics:lowerLimit", 0.0),
                    ("physics:upperLimit", profile.gripperFullyClosedPosition),
                ),
            )
        elif name in ("left_outer_finger_joint", "right_outer_finger_joint"):
            setDriveAttrs(
                prim,
                profile.gripperMaxForce,
                profile.outerFingerParallelStiffness,
                profile.gripperDamping,
            )
        elif "finger" in name or "knuckle" in name:
            for attr_name in (
                "drive:angular:physics:maxForce",
                "drive:angular:physics:stiffness",
                "drive:angular:physics:damping",
                "drive:angular:physics:targetVelocity",
            ):
                attr = prim.GetAttribute(attr_name)
                if attr and attr.IsValid():
                    attr.Set(0.0)
    if not found_finger_joint:
        raise RuntimeError(f"Missing Robotiq finger_joint under {gripper_root.GetPath()}")


def _configureClosedLoop(stage, prim_path, profile):
    from pxr import Gf, PhysxSchema, Sdf, Usd, UsdPhysics

    gripper = f"{prim_path}/{profile.gripperPrim}"
    base_path = f"{gripper}/base_link"
    joint_root_path = f"{gripper}/Joints"
    requireStagePrim(stage, base_path)
    joint_root = requireStagePrim(stage, joint_root_path)
    for body_path in (f"{gripper}/left_inner_knuckle", f"{gripper}/right_inner_knuckle"):
        requireStagePrim(stage, body_path)

    def configureJointCommon(prim, exclude_from_articulation):
        _setAttr(
            prim,
            "physics:excludeFromArticulation",
            bool(exclude_from_articulation),
            Sdf.ValueTypeNames.Bool,
        )
        _setAttr(prim, "physics:jointEnabled", True, Sdf.ValueTypeNames.Bool)
        if not prim.HasAPI(PhysxSchema.PhysxJointAPI):
            PhysxSchema.PhysxJointAPI.Apply(prim)

    passive_joint_specs = (
        (
            "left_inner_knuckle_joint",
            f"{gripper}/left_inner_knuckle",
            (0.0, -0.0127, 0.06142),
            (0.5, 0.5, -0.5, -0.5),
        ),
        (
            "right_inner_knuckle_joint",
            f"{gripper}/right_inner_knuckle",
            (0.0, 0.0127, 0.06142),
            (0.5, -0.5, 0.5, -0.5),
        ),
    )
    for name, body_path, local_pos, local_rot in passive_joint_specs:
        joint_path = f"{joint_root_path}/{name}"
        joint_prim = stage.GetPrimAtPath(joint_path)
        if not joint_prim.IsValid():
            joint_prim = UsdPhysics.RevoluteJoint.Define(stage, joint_path).GetPrim()
        joint = UsdPhysics.RevoluteJoint(joint_prim)
        joint.GetBody0Rel().SetTargets([Sdf.Path(base_path)])
        joint.GetBody1Rel().SetTargets([Sdf.Path(body_path)])
        joint.CreateAxisAttr().Set(UsdPhysics.Tokens.z)
        joint.CreateLocalPos0Attr().Set(Gf.Vec3f(*local_pos))
        joint.CreateLocalPos1Attr().Set(Gf.Vec3f(*local_pos))
        rot = Gf.Quatf(local_rot[0], Gf.Vec3f(*local_rot[1:]))
        joint.CreateLocalRot0Attr().Set(rot)
        joint.CreateLocalRot1Attr().Set(rot)
        configureJointCommon(joint_prim, exclude_from_articulation=True)

    for prim in Usd.PrimRange(joint_root):
        if prim.GetName() in (
            "left_inner_finger_knuckle_joint",
            "right_inner_finger_knuckle_joint",
        ):
            configureJointCommon(prim, exclude_from_articulation=False)


def configureRobotiqContactMaterial(stage, prim_path, profile):
    """Bind a high-friction contact material to the gripper's collision geometry."""
    from omni.physx.scripts import physicsUtils
    from pxr import PhysxSchema, Usd, UsdPhysics

    root = requireStagePrim(stage, f"{prim_path}/{profile.gripperPrim}")
    _definePhysicsMaterial(
        stage,
        profile.gripperContactMaterialPath,
        profile.gripperStaticFriction,
        profile.gripperDynamicFriction,
    )

    for prim in Usd.PrimRange(root):
        path = str(prim.GetPath())
        if prim.IsInstance() and (path.endswith("/visuals") or "/visuals/" in path):
            prim.SetInstanceable(False)

    collision_prims = _collisionPrims(root)
    for prim in collision_prims:
        if prim.IsInstanceProxy():
            raise RuntimeError(
                f"Could not bind gripper contact material to instance proxy: {prim.GetPath()}"
            )
        physicsUtils.add_physics_material_to_prim(
            stage, prim, profile.gripperContactMaterialPath
        )
        collision_api = (
            UsdPhysics.CollisionAPI(prim)
            if prim.HasAPI(UsdPhysics.CollisionAPI)
            else UsdPhysics.CollisionAPI.Apply(prim)
        )
        collision_api.CreateCollisionEnabledAttr().Set(True)
        physx_collision_api = PhysxSchema.PhysxCollisionAPI.Apply(prim)
        physx_collision_api.CreateContactOffsetAttr().Set(float(profile.contactOffset))
        physx_collision_api.CreateRestOffsetAttr().Set(float(profile.restOffset))
    if not collision_prims:
        raise RuntimeError(
            f"No collision geometry found for Robotiq gripper under {root.GetPath()}"
        )


def configureRobotiqPickObjectContact(stage, prim_paths, profile):
    """Make rigid objects graspable: contact material, CCD, mass, and offsets."""
    from omni.physx.scripts import physicsUtils
    from pxr import PhysxSchema, UsdPhysics

    _definePhysicsMaterial(
        stage,
        profile.objectContactMaterialPath,
        profile.objectStaticFriction,
        profile.objectDynamicFriction,
    )

    for prim_path in prim_paths:
        root = requireStagePrim(stage, prim_path)
        rigid_api = PhysxSchema.PhysxRigidBodyAPI.Apply(root)
        rigid_api.CreateEnableCCDAttr().Set(True)
        rigid_api.CreateSleepThresholdAttr().Set(0.0)

        mass_api = (
            UsdPhysics.MassAPI(root)
            if root.HasAPI(UsdPhysics.MassAPI)
            else UsdPhysics.MassAPI.Apply(root)
        )
        mass_api.CreateMassAttr().Set(float(profile.pickObjectMassKg))

        collision_prims = _collisionPrims(root)
        if not collision_prims:
            raise RuntimeError(
                f"No collision geometry found for pick object: {prim_path}"
            )
        for prim in collision_prims:
            if prim.IsInstanceProxy():
                raise RuntimeError(
                    f"Could not bind pick object material to instance proxy: {prim.GetPath()}"
                )
            physicsUtils.add_physics_material_to_prim(
                stage, prim, profile.objectContactMaterialPath
            )
            collision_api = PhysxSchema.PhysxCollisionAPI.Apply(prim)
            collision_api.CreateContactOffsetAttr().Set(float(profile.contactOffset))
            collision_api.CreateRestOffsetAttr().Set(float(profile.restOffset))
