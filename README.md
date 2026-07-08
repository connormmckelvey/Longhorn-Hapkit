![Overview](/_DOCS/overview.png)

# The Longhorn Hapkit
### A Complete Haptic Robotics Education Ecosystem
---
###### Written by Ross Neuman and Connor McKelvey for the Human Enabled Robotics Lab at UT Austin under Professor Ann Fey.


> **A note to the reader:** The Longhorn Hapkit aims to provide a complete toolset to enable anyone to learn robotics through the interdisplinary and universal sense of touch. These low-cost devices enable students to learn mechanical design, electronics, and software engineering. Hopefully the provided documents supply an ample jumping off point for educators and ambitious students alike to look deeper into the field of robotics and create their very own projects and improvements to our ecosystem.

#### This Project Includes:
- 1 Degree of Freedom Haptic device design
    - A simple first device to build and learn what haptics is, use this to render your first artifical wall, dampener, or spring!
- 2 Degree of Freedom Haptic device design
    - Once you've mastered the 1-DOF enviroments, combine two of them into our 2-DOF design opening a world a possibilies. From teleoperation to pong games, use this device to make games or more complex simulations!
- Haplink implementation for device interfacing with Python

#### Repository Structure
```
DOCS/
    * supplemental material, diagrams, bill of materials
firmware/
    * files are numbered coresponding to /python scripts
    1DOF/
    2DOF/
    includes/ 
        * header files used by various scripts
python/
    1DOF/
    2DOF/
    tools/ 
        *helper scripts (e.g. to find connect ports)
README.md
platformio.ini *configuration file showing dependencies
```

<table>
  <tr>
    <th colspan="2" align="center">Environment Setup</th>
  </tr>
  <tr>
    <td width="50%"><b>Arduino IDE Setup</b></td>
    <td width="50%"><b>PlatformIO Setup</b></td>
  </tr>
  <tr>
    <td valign="top">
      1. Download and install the <b>Arduino IDE</b>.<br><br>
      2. Open the <b>Library Manager</b> from the left sidebar.<br><br>
      3. Search for <b>Haplink</b> by Connor McKelvey.<br><br>
      4. Select version <b>1.0.3</b> and click <b>Install</b>.<br><br>
      5. Select <b>Arduino Uno</b> as your board.<br><br>
      5. Copy the contents of <code>1_basic.cpp</code> into the main window and hit compile.<br><br>
      6. Write code!<br><br>
      Note: you will need to use another IDE to run future python scripts 
    </td>
    <td valign="top">
      1. Download and install <b>VS Code</b> with the <b>PlatformIO Extension</b>.<br><br>
      2. Open the <b>PlatformIO Home</b> and create a new project.<br><br>      
      3. Open the <b>PlatformIO Home</b> and click on <b>Libraries</b>.<br><br>
      4. Search for <b>Haplink</b> by Connor McKelvey.<br><br>
      5. Copy <code>1_basic.cpp</code> into the <code>src/</code> folder of the project<br><br>
      6. Run <code>PlatformIO:Upload</code> and watch the magic happen.<br><br>
      7. When you are ready to interface with Python, navigate to <a href="https://github.com/connormmckelvey/Haplink">github.com/connormmckelvey/Haplink</a> and follow the instructions for PlatformIO install.
    </td>
  </tr>
</table>
