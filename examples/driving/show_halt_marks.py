"""Draw a small junction with a stop, a yield, and a traffic light in each direction.

Run from the repository root:

    .venv/bin/python examples/driving/show_halt_marks.py
"""

import tempfile
from pathlib import Path

import matplotlib.pyplot as plt

from scenic.domains.driving.roads import Network

LANES = """
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <left>
          <lane id="1" type="driving" level="false">
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </left>
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
"""

MAP = f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="6" name="halt_marks" version="1.0"/>
  <road name="West Approach" length="20.0" id="1" junction="-1">
    <link><successor elementType="junction" elementId="100"/></link>
    <planView>
      <geometry s="0" x="0.0" y="0.0" hdg="0.0" length="20.0"><line/></geometry>
    </planView>
    <lanes>{LANES}</lanes>
    <signals>
      <signal s="6.0" t="1.75" id="10" name="stop" dynamic="no"
              orientation="-" zOffset="2" type="206" country="OpenDRIVE"
              subtype="-1" value="-1"/>
      <signal s="12.0" t="-1.75" id="11" name="yield" dynamic="no"
              orientation="+" zOffset="2" type="205" country="OpenDRIVE"
              subtype="-1" value="-1"/>
      <signal s="14.0" t="-5.5" id="12" name="light" dynamic="yes"
              orientation="+" zOffset="5" type="1000001" country="OpenDRIVE"
              subtype="-1" value="-1"/>
    </signals>
  </road>
  <road name="East Exit" length="20.0" id="2" junction="-1">
    <link><predecessor elementType="junction" elementId="100"/></link>
    <planView>
      <geometry s="0" x="32.0" y="0.0" hdg="0.0" length="20.0"><line/></geometry>
    </planView>
    <lanes>{LANES}</lanes>
    <signals>
      <signal s="6.0" t="5.5" id="13" name="light_return" dynamic="yes"
              orientation="-" zOffset="5" type="1000001" country="OpenDRIVE"
              subtype="-1" value="-1"/>
    </signals>
  </road>
  <road name="Connector" length="12.0" id="10" junction="100">
    <link>
      <predecessor elementType="road" elementId="1" contactPoint="end"/>
      <successor elementType="road" elementId="2" contactPoint="start"/>
    </link>
    <planView>
      <geometry s="0" x="20.0" y="0.0" hdg="0.0" length="12.0"><line/></geometry>
    </planView>
    <lanes>
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><predecessor id="-1"/><successor id="-1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
  <road name="Return Connector" length="12.0" id="11" junction="100">
    <link>
      <predecessor elementType="road" elementId="2" contactPoint="start"/>
      <successor elementType="road" elementId="1" contactPoint="end"/>
    </link>
    <planView>
      <geometry s="0" x="32.0" y="0.0" hdg="3.141592653589793" length="12.0"><line/></geometry>
    </planView>
    <lanes>
      <laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0">
        <center><lane id="0" type="none" level="false"/></center>
        <right>
          <lane id="-1" type="driving" level="false">
            <link><predecessor id="1"/><successor id="1"/></link>
            <width sOffset="0" a="3.5" b="0" c="0" d="0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
  </road>
  <junction name="J" id="100">
    <connection id="0" incomingRoad="1" connectingRoad="10" contactPoint="start">
      <laneLink from="-1" to="-1"/>
    </connection>
    <connection id="1" incomingRoad="2" connectingRoad="11" contactPoint="start">
      <laneLink from="1" to="-1"/>
    </connection>
  </junction>
</OpenDRIVE>
"""


def main():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "map.xodr"
        path.write_text(MAP)
        network = Network.fromFile(path, useCache=False)
    # signalPosition="pole" draws each traffic light at its physical s/t.
# The default, "halt", draws it on the stop line of the lanes it controls.
network.show()
    plt.gca().set_aspect("equal")
    plt.show()


if __name__ == "__main__":
    main()
