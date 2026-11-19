from simulation_interfaces.srv import SetSimulationState, ResetSimulation, StepSimulation
from simulation_interfaces.msg import SimulationState

import rclpy


def PauseGazebo(node, client):
    """
    Pauses Gazebo
    """

    request = SetSimulationState.Request()

    request.state = SimulationState()
    request.state.state = SimulationState.STATE_PAUSED

    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future)
    if future.result() is not None:
        print('response: %r' % future.result())
    else:
        raise RuntimeError(
            'exception while calling service: %r' % future.exception())
    return


def UnpauseGazebo(node, client):
    """
    Unpauses Gazebo
    """
    request = SetSimulationState.Request()

    request.state = SimulationState()
    request.state.state = SimulationState.STATE_PLAYING

    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future)
    if future.result() is not None:
        print('response: %r' % future.result())
    else:
        raise RuntimeError(
            'exception while calling service: %r' % future.exception())
    return

def TakeStep(node, client):
    """
    Steps the simulation forward once
    """
    request = StepSimulation.Request()
    # 1000 seems to be the max
    request.steps = 1000

    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future)
    if future.result() is not None:
        print('response: %r' % future.result())
    else:
        raise RuntimeError(
            'exception while calling service: %r' % future.exception())
    return

def ResetGazeboWorld(node, client):
    """
    Resets the Gazebo world. Simulation time is NOT reset
    Probably the Reset function that you want
    """
    request = ResetSimulation.Request()

    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future)
    if future.result() is not None:
        print('response: %r' % future.result())
    else:
        raise RuntimeError(
            'exception while calling service: %r' % future.exception())
    return
