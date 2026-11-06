"""The SampleChecker class and it's implementations."""

from abc import ABC, abstractmethod
from collections import deque
import time

from scenic.core.distributions import RejectionException
from scenic.core.requirements import BlanketCollisionRequirement, IntersectionRequirement


class SampleChecker(ABC):
    def __init__(self):
        self.requirements = None

    def __eq__(self, value):
        # We don't check self.requirements, since it can have different values
        # depending on what soft requirements are selected.
        return type(self) == type(value)

    def setRequirements(self, requirements):
        assert self.requirements is None
        self.requirements = tuple(requirements)

    @abstractmethod
    def checkRequirementsInner(self, sample):
        pass

    def checkRequirements(self, sample):
        assert self.requirements is not None
        try:
            return self.checkRequirementsInner(sample)
        except RejectionException as e:
            return e


class BasicChecker(SampleChecker):
    """Basic requirement checker.

    Evaluates requirements in order, with a tiny bit of tuning.
    """

    def __init__(self, initialCollisionCheck):
        super().__init__()
        self.initialCollisionCheck = initialCollisionCheck

    def setRequirements(self, requirements):
        target_reqs = []
        for req in requirements:
            if req.optional:
                # Basic checker ignores optional requirements unless otherwise noted.
                if (
                    isinstance(req, BlanketCollisionRequirement)
                    and self.initialCollisionCheck
                    and sum(isinstance(r, IntersectionRequirement) for r in requirements)
                    >= 3
                ):
                    target_reqs.append(req)
            else:
                target_reqs.append(req)

        super().setRequirements(target_reqs)

    def checkRequirementsInner(self, sample):
        for req in self.requirements:
            if req.active and req.falsifiedBy(sample):
                return req.violationMsg

        return None


class WeightedAcceptanceChecker(SampleChecker):
    """Picks the requirement with the lowest time-weighted acceptance chance.

    Incentivizes exploration by initializing all buffer values to 0.

    Args:
        bufferSize: Max samples to use when calculating time-weighted
            rejection chance.
    """

    def __init__(self, bufferSize=10):
        super().__init__()
        self.bufferSize = bufferSize
        self.buffers = None
        self.bufferSums = None

    def setRequirements(self, requirements):
        super().setRequirements(requirements)

        self.buffers = {req: deque() for req in self.requirements}
        self.bufferSums = {req: (0, 0) for req in self.requirements}
        for req in self.requirements:
            self.buffers[req].extend([(0, 0)] * self.bufferSize)

    def checkRequirementsInner(self, sample):
        for req in self.sortedRequirements():
            # Evaluate the requirement with timing info.
            start = time.perf_counter()
            rejected = req.falsifiedBy(sample)
            # Create metrics (Accepted, Time Taken)
            metrics = (int(not rejected), time.perf_counter() - start)

            self.updateMetrics(req, metrics)

            if rejected:
                return req.violationMsg

        return None

    def sortedRequirements(self):
        """Return the list of requirements in sorted order"""
        # Extract and sort active requirements
        reqs = [req for req in self.requirements if req.active]
        reqs.sort(key=self.getRequirementCost)

        # Remove any optional requirements at the end of the list, since they're useless
        while reqs and reqs[-1].optional:
            reqs.pop()

        return reqs

    def updateMetrics(self, req, new_metrics):
        """Update the metrics for a given requirement"""
        # Update buffer
        target_buffer = self.buffers[req]
        old_metrics = target_buffer.popleft()
        target_buffer.append(new_metrics)

        # Unpack values
        sum_acc, sum_time = self.bufferSums[req]
        old_acc, old_time = old_metrics
        new_acc, new_time = new_metrics

        # Update sums
        sum_acc += new_acc - old_acc
        sum_time += new_time - old_time
        self.bufferSums[req] = (sum_acc, sum_time)

    def getRequirementCost(self, req):
        # Expected cost of a requirement is average runtime divided by rejection probability;
        # if estimated rejection probability is zero, break ties using runtime.
        sum_acc, sum_time = self.bufferSums[req]
        runtime = sum_time / self.bufferSize
        rej_prob = 1 - (sum_acc / self.bufferSize)
        if rej_prob > 0:
            return (runtime / rej_prob, 0)
        else:
            return (float("inf"), runtime)
