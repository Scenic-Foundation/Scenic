"""Functionality for interfacing the Scenic driving domain with OpenScenario."""

import math
import os
import warnings

from scenic.core.vectors import Vector


def toOpenScenario(
    simulation,
    mapPath=None,
    scenarioName="ScenicScenario",
):
    """Export a `Simulation` as a `scenariogeneration.xosc.scenario <https://pyoscx.github.io/scenariogeneration/xosc/scenario.html>`_ object.

    Args:
        simulation: The `Simulation` to be exported to XOSC
        mapPath: The path to the XODR map used to run the simulation. If
            one is not provided the `map` param of the scenario is used.
        scenarioName: The scenario name to use in the generated XOSC file.

    .. versionadded:: unreleased
    """
    try:
        import scenariogeneration
        from scenariogeneration import ScenarioGenerator, xosc
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            "The `scenariogeneration` package is required to use Scenic's XOSC export functionality."
        ) from e

    if simulation.result is None:
        raise RuntimeError("Cannot export incomplete scenario to OpenScenario XML")

    scene = simulation.scene
    scenario = scene.scenario

    if len(scene.objects) != len(simulation.trajectory[-1].positions):
        raise RuntimeError("Cannot export scenario with dynamically created objects.")

    # Create catalog
    xosc_catalog = xosc.Catalog()

    # Create parameters
    xosc_paramdec = xosc.ParameterDeclarations()

    # Extract map
    if mapPath is None:
        if "map" not in scenario.params:
            raise ValueError(
                "No `mapPath` provided and scenario does not have a `map` parameter defined."
            )
        mapPath = os.path.abspath(scenario.params["map"])
    xosc_road = xosc.RoadNetwork(roadfile=mapPath)

    # Create entitities
    entities = xosc.Entities()
    xosc_objects = {}
    for obj_i, obj in enumerate(scene.objects):
        if getattr(obj, "isVehicle", False):
            obj_name = getattr(obj, "name", f"Vehicle{obj_i}")
            veh_bb = xosc.BoundingBox(
                obj.width,
                obj.length,
                obj.height,
                0,
                0,
                0,
            )
            veh_fa = xosc.Axle(
                obj.maxSteeringAngle,
                obj.wheelDiameter,
                obj.trackWidth,
                obj.wheelbase,
                obj.groundClearance,
            )
            veh_ra = xosc.Axle(
                obj.maxSteeringAngle,
                obj.wheelDiameter,
                obj.trackWidth,
                0,
                obj.groundClearance,
            )
            xosc_obj = xosc.Vehicle(
                name=obj_name,
                vehicle_type=xosc.VehicleCategory.car,
                boundingbox=veh_bb,
                frontaxle=veh_fa,
                rearaxle=veh_ra,
                max_speed=obj.maxSpeed,
                max_acceleration=obj.maxAcceleration,
                max_deceleration=obj.maxDeceleration,
                mass=None,
                model3d=None,
                max_acceleration_rate=None,
                max_deceleration_rate=None,
                role=None,
            )
        elif getattr(obj, "isPedestrian", False):
            obj_name = getattr(obj, "name", f"Pedestrian{obj_i}")
            ped_bb = xosc.BoundingBox(
                obj.width,
                obj.length,
                obj.height,
                0,
                0,
                0,
            )
            xosc_obj = xosc.Pedestrian(
                name=obj_name,
                mass=obj.mass,
                boundingbox=ped_bb,
                category=xosc.PedestrianCategory.pedestrian,
                model=None,
                role=None,
            )
        else:
            warnings.warn(
                f"Object {obj} of unsupported type is being ignored during XOSC export."
            )
            continue

        xosc_objects[obj] = xosc_obj
        entities.add_scenario_object(obj_name, xosc_obj)

    # Helper function
    def pos_to_WorldPosition(obj, pos, yaw):
        # XOSC Reference point is back axle, so we must translate Scenic's
        # convention to this.
        state_position = (
            pos.offsetRotated(yaw, Vector(0, -0.5 * obj.wheelbase, 0))
            if obj.isVehicle
            else pos
        )
        state_orientation = yaw + math.radians(90)
        return xosc.WorldPosition(
            x=state_position.x,
            y=state_position.y,
            z=state_position.z,
            h=state_orientation,
        )

    # Initial states
    init = xosc.Init()

    for obj, xosc_obj in xosc_objects.items():
        obj_init_action = xosc.TeleportAction(
            pos_to_WorldPosition(obj, obj.position, obj.heading)
        )
        init.add_init_action(xosc_obj.name, obj_init_action)

    # Dynamics
    xosc_act = xosc.Act(
        "MainAct",
        xosc.ValueTrigger(
            "StartSimulation",
            0,
            xosc.ConditionEdge.none,
            xosc.SimulationTimeCondition(0, xosc.Rule.greaterThan),
        ),
    )

    for obj_i, (obj, xosc_obj) in enumerate(xosc_objects.items()):
        action_times = []
        action_positions = []
        for t, states in enumerate(simulation.trajectory):
            action_positions.append(
                pos_to_WorldPosition(
                    obj, states.positions[obj_i], states.orientations[obj_i].yaw
                )
            )
            action_times.append(simulation.timestep * t)

        polyline = xosc.Polyline(time=action_times, positions=action_positions)
        trajectory = xosc.Trajectory(name=f"Trajectory_{xosc_obj.name}", closed=False)
        trajectory.add_shape(polyline)

        traj_action = xosc.FollowTrajectoryAction(
            trajectory=trajectory,
            following_mode=xosc.FollowingMode.position,
            reference_domain=xosc.ReferenceContext.absolute,
            scale=1,
            offset=0,
        )

        event = xosc.Event(f"Event_{xosc_obj.name}", xosc.Priority.override)
        event.add_trigger(
            xosc.ValueTrigger(
                f"TimeTrigger_{xosc_obj.name}",
                0,
                xosc.ConditionEdge.none,
                xosc.SimulationTimeCondition(0, xosc.Rule.greaterThan),
            )
        )
        event.add_action(f"Action_{xosc_obj.name}", action=traj_action)

        maneuver = xosc.Maneuver("Maneuver_{xosc_obj.name}")
        maneuver.add_event(event)

        manuever_group = xosc.ManeuverGroup(f"ManeuverGroup_{xosc_obj.name}")
        manuever_group.add_maneuver(maneuver)
        manuever_group.add_actor(xosc_obj.name)

        xosc_act.add_maneuver_group(manuever_group)

    # Create storyboard
    xosc_sb = xosc.StoryBoard(
        init,
        xosc.ValueTrigger(
            "StopSimulation",
            0,
            xosc.ConditionEdge.rising,
            xosc.SimulationTimeCondition(
                simulation.currentRealTime, xosc.Rule.greaterThan
            ),
            "stop",
        ),
    )
    xosc_sb.add_act(xosc_act)

    # Create scenario
    xosc_scenario = xosc.Scenario(
        scenarioName,
        "Scenic",
        xosc_paramdec,
        entities=entities,
        storyboard=xosc_sb,
        roadnetwork=xosc_road,
        catalog=xosc_catalog,
    )

    return xosc_scenario
