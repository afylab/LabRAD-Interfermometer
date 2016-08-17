# Copyright []
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
### BEGIN NODE INFO
[info]
name = Cryo Positioning Systems Controller (CPSC) Server
version = 1.0
description = Communicates with the CPSC which controls the JPE piezo stacks. 
Must be placed in the same directory as cacli.exe in order to work. 
### END NODE INFO
"""

import subprocess
import re

from labrad.server import LabradServer, setting
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value
import time
import numpy as np

class CPSCServer(LabradServer):
    name = "CPSC Server"    # Will be labrad name of server

    @inlineCallbacks
    def initServer(self):  # Do initialization here
        self.device_detected = False
        #Array of devices and their information. ADDR, Device Name, CH, and Type info. 
        self.device_list = ['ADDR','CHANNEL','DEVICE NAME','TAG', 'TYPE INFO']
        
        #Distance between pivot point and top of sample given in mm. 
        #This value changes with geometry of sample loaded on piezos. 
        self.h = 33.9
        #radius given in mm. This value should be constant.
        self.R = 15.0
        
        #Matrix T1 goes from xyz coordinates to channel 1, 2, 3 coordinates. 
        self.T1 = [[-self.R * np.sqrt(3) / (2*self.h), self.R / (2*self.h), 1],[0,-self.R/(2*self.h),1],[-self.R * np.sqrt(3) / (2*self.h), self.R / (2*self.h), 1]]
        
        #Matrix T2 goes from channel coordinates back to xyz coordinates and gives 
        yield self.detect_device()
        print "Server initialization complete"
        
    @setting(100,returns = 'b')
    def detect_device(self):
        resp = yield subprocess.check_output("cacli modlist")
        
        if resp.startswith("ERROR: DEVICE NOT FOUND"):
            print "CPSC not detected. Ensure controller is connected to computer and channel is set to EXT, then run detect device method." 
            self.device_detected = False
            self.device_list = ['ADDR','CHANNEL','DEVICE NAME','TAG', 'TYPE INFO']
            returnValue(False)
        elif resp.startswith("STATUS : INQUIRY OF INSTALLED MODULES"):
            print "CPSC detected. Communication active."
            self.device_detected = True
            self.device_list = ['ADDR','CHANNEL','DEVICE NAME','TAG', 'TYPE INFO']
            for i in range (1,7):
                slot = self.find_between(resp,'SLOT ' + str(i) + ' : ','\r\n')
                if slot != " ":
                    
                    DEV_NAME = self.find_between(resp,'SLOT ' + str(i) + ' : ','ADR')
                    ADDR = i
                    if DEV_NAME.startswith("Cryo Actuator Driver Module (CADM)"):
                        for j in range (1,4):
                            cntx = None
                            [TYPE,TAG] = yield self.get_actuator_info(cntx,i,j)
                            CH = j
                            self.device_list.append([ADDR,CH,DEV_NAME,TAG,TYPE])
                    #For other devices, add info here         
                    
                    print "Slot " + str(i) + " device added to device list."
            #load up device_list with all pertinent information
            print self.device_list
            returnValue(True)
            
    @setting(101, returns='s')
    def get_module_list(self, c):
        """Command to list the automatically detected modules in the controller."""
        if self.device_detected == True:
            resp = yield subprocess.check_output("cacli modlist")
        else:
            resp = "Device not connected."
            print "Device not connected. "
            #Eventually make this actually throw an error instead of printing something
        returnValue(resp)
            
    @setting(102, ADDR='i', returns='s')
    def get_module_info(self, c, ADDR):
        """Requests the module description and available output channels.
        Input ADDR is the module location (integer 1 through 6). """
        if self.device_detected == True:
            resp = yield subprocess.check_output("cacli DESC "+str(ADDR))
        else:
            resp = "Device not connected."
            print "Device not connected. "
            #Eventually make this actually throw an error instead of printing something
        returnValue(resp)
        
    @setting(103, ADDR='i', CH = 'i', returns='*s')
    def get_actuator_info(self, c, ADDR, CH):
        """Requests information about a user defined Tags (name) or set actuator Types. 
        Input ADDR is the module location (integer 1 through 6). 
        Input CH is the module channel, integer 1 through 3.
        Returns array of strings. First element is the Type. Second element is the Tag."""
        if self.device_detected == True:
            resp = yield subprocess.check_output("cacli INFO "+str(ADDR) + " " + str(CH))
            type = self.find_between(resp,"TYPE :","\r\n")
            tag = self.find_between(resp,"TAG  :","\r\n")
            info = [type, tag]
        else:
            resp = "Device not connected."
            info = [resp, resp]
            #Eventually make this actually throw an error instead of printing something
        returnValue(info)
        
    @setting(104, ADDR='i', CH = 'i', TYPE = 's', TEMP = 'i', DIR = 'i', FREQ = 'i',
                REL = 'i', STEPS = 'i', returns='s')
    def move(self, c, ADDR, CH, TYPE, TEMP, DIR, FREQ, REL, STEPS):
        """Moves specified actuator with specified parameters. ADDR and CH specify the 
        module address (1 through 6) and channel (1 through 3). 
        TYPE specifies the cryo actuator model. TEMP is the nearest integer temperature
        (0 through 300). DIR determines CW (1) vs CWW (0) stack rotation. 
        FREQ is the interger frequency of operation input in Hertz. 
        REL is the piezo step size parameter input. Value is a percentage (0-100%).
        STEPS is the number of actuation steps. Range is 0 to 50000, where 0 is used for
        infinite movement. 
        """
        if self.device_detected == True:
            #Add input checks
            resp = yield subprocess.check_output("cacli MOV "+str(ADDR) + " " + str(CH)
             + " " + TYPE + " " + str(TEMP) + " " + str(DIR) + " " + str(FREQ) + " " +
             str(REL) + " " + str(STEPS))
            print resp
        else:
            resp = "Device not connected."
            print "Device not connected. "
            #Eventually make this actually throw an error instead of printing something
        returnValue(resp)
        
    @setting(105, ADDR = 'i', returns = 's')
    def stop(self,c,ADDR):
        """Stops movement of the actuator at the specified address."""
        if self.device_detected == True:
            resp = yield subprocess.check_output("cacli STP " + str(ADDR))
            print resp
        else:
            resp = "Device not connected."
            print "Device not connected. "
        returnValue(resp)
        
    @setting(106, ADDR = 'i', returns = '*s')
    def status(self,c,ADDR):
        """Requests the status of the amplifier at provided address. Returns Moving
        or Stop in the first element of array. In addition, amplifier Failsage State
        is shown. If any error of the amplifier occurs (red status LED on front panel)
        the cause of the error may be requested via this command."""
        if self.device_detected == True:
            resp = yield subprocess.check_output("cacli STP " + str(ADDR))
            print resp
        else:
            resp = "Device not connected."
            print "Device not connected. "
        returnValue(resp)
        
    @setting(107, returns = 'v[]')
    def get_height(self,c):
        """Returns the height from the sample to the pivot location. """
        returnValue(self.h)
        
    @setting(108, h = 'v[]', returns = 'v[]')
    def set_height(self,c, h):
        """Sets and returns the height from the sample to the pivot location. """
        self.h = h
        self.T1 = [[-self.R * np.sqrt(3) / (2*self.h), self.R / (2*self.h), 1],[0,-self.R/(2*self.h),1],[-self.R * np.sqrt(3) / (2*self.h), self.R / (2*self.h), 1]]
        returnValue(self.h)
        
    @setting(109, ADDR = 'i', returns = 's')
    def center(self,c, ADDR):
        """Centers the piezos specified by ADDR in order to keep track of position. This will run the piezos through their
        full movement range. Make sure this is only called with no sensitive sample and be destroyed."""
        #DEV referes to the list of devices
        returnValue('Success!')
    
    @setting(110, ADDR = 'i', TEMP = 'i', DIR = 'i', FREQ = 'i', REL = 'i', XYZ = '*i', returns = 's')
    def move_xyz(self,c, ADDR, TEMP, DIR, FREQ, REL, XYZ):
        """Request CADM move sample in the according to the arbitrary vector XYZ. XYZ should be a 3 element list 
        with the number of steps to be taken in the x, y, and z direction respectively. Output returns the number
        of steps taken in the x, y, and z directions (not necessarily equal), and the number of steps taken
        in radial directions."""
        
        vec = np.dot(self.T1,XYZ)
        
        vec = [round(x) for x in vec]
        
        yield self.move(ADDR, 1, 'CA1801', TEMP, DIR, FREQ, REL, VEC[0])
        yield self.move(ADDR, 2, 'CA1801', TEMP, DIR, FREQ, REL, VEC[1])
        yield self.move(ADDR, 3, 'CA1801', TEMP, DIR, FREQ, REL, VEC[2])
        
        returnValue('Success!')
    
    
    def find_between(self, s, start, end):
        try:
            result = re.search('%s(.*)%s' % (start, end), s).group(1)
        except:
            result = ""
        return result
        
__server__ = CPSCServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)