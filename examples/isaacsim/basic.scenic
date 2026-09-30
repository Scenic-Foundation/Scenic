model scenic.simulators.isaac.model

ego = new IsaacSimObject at (-1, 0, 10), with shape ConeShape(),
        with width 2,
        with length 2,
        with height 1.5,
        facing (-90 deg, 45 deg, 0),
        with color (0, 1, 0),
        with physics False

chair = new IsaacSimObject at (4,0,2),
            with shape MeshShape.fromFile(localPath("../../assets/meshes/chair.obj.bz2"),
                initial_rotation=(0,90 deg,0), dimensions=(1,1,1)), with physics False,
            with color (1, 0, 0)

plane_shape = MeshShape.fromFile(path=localPath("../../assets/meshes/classic_plane.obj.bz2"), initial_rotation=(-90 deg, 0, 0))

plane = new IsaacSimObject left of chair by 1,
            with shape plane_shape,
            with width 2,
            with physics False,
            with length 2,
            with height 1,
            facing directly toward ego
