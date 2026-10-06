import rospy
import time
import numpy as np

behavior WaitForTime(wait_time):
    t0 = time.time()
    t1 = t0
    while t1 - t0 < wait_time:
        wait
        t1 = time.time()
    
behavior WaitForTimeROS(wait_time):
    """
    Wait for time in terms of ros time
    """
    t0 = rospy.get_rostime()
    t1 = rospy.get_rostime()
    while (t1.secs + t1.nsecs/(10**9) - t0.secs - t0.nsecs/(10**9)) < wait_time:
        wait
        t1 = rospy.get_rostime()

