# Only import Airsim simulator if the airsim package is installed; otherwise the
# import would raise an exception.
airsim = None
try:
    import airsim
except ImportError:
    pass
if airsim:
    from .simulator import AirSimSimulator
del airsim
