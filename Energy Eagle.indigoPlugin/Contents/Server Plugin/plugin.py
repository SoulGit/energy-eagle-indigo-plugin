#! /usr/bin/env python
import re
import time
import socket
import requests
from lxml import objectify
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

##To Do: Implement plugin update version check

def requestsRetrySession(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None
):
    """Add retry functionality to requests"""
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    return session

class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        """Initialize Plugin Class"""
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.debug = pluginPrefs.get("showDebugInfo", False)
        self.debugLog(u"Initializing Plugin.")
        self.deviceList = []

    def __del__(self):
        """Delete Plugin"""
        self.debugLog(u"Stopping plugin.")
        indigo.PluginBase.__del__(self)

    def deviceStartComm(self, device):
        """Device Start Communication"""
        self.debugLog(u"Starting device: " + device.name)
        if device.id not in self.deviceList:
            self.deviceList.append(device.id)

    def deviceStopComm(self, device):
        """Device Stop Communication"""
        self.debugLog(u"Stopping device: " + device.name)
        if device.id in self.deviceList:
            self.deviceList.remove(device.id)

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        """Validate Device Configuration"""
        self.debugLog(u"validateDeviceConfigUi called.  Values: \n" + str(valuesDict))

        error = False
        errorsDict = indigo.Dict()
        errorsDict['showAlertText'] = ""

        # EAGLE device
        if typeId == "EAGLE":
            # IP Address validation...
            ipAddress = valuesDict.get('ipAddress', "")
            if ipAddress == "":
                error = True
                errorsDict['ipAddress'] = u"Please enter an IP address or local host name."
                errorsDict['showAlertText'] += errorsDict['ipAddress'] + "\n\n"
            else:
                # Something was entered for the IP Address. Try it out.
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(5)        # Allow the connection to timeout.
                    s.connect((ipAddress, 80))
                    self.debugLog(u"Connection to \"" + ipAddress + "\" verified.")
                    # Create the "address" property for the device.
                    valuesDict['address'] = ipAddress
                except Exception, e:
                    error = True
                    # Close the connection.
                    s.close()
                    errorsDict['ipAddress'] = u"Unable to connect to \"" + ipAddress + u"\". Error: " + str(e)
                    errorsDict['showAlertText'] += errorsDict['ipAddress'] + "\n\n"
                # Close the connection.
                s.close()

                if not error:
                    # Try and connect to the local API
                    cloudID = valuesDict.get('cloudID', "")
                    if cloudID == "":
                        error = True
                        errorsDict['cloudID'] = u"Please enter CloudID."
                        errorsDict['showAlertText'] += errorsDict['cloudID'] + "\n\n"

                    installCode = valuesDict.get('installCode', "")
                    if installCode == "":
                        error = True
                        errorsDict['installerID'] = u"Please enter Install Code."
                        errorsDict['showAlertText'] += errorsDict['installerID'] + "\n\n"

                    r = requests.post('http://' + ipAddress + '/cgi-bin/post_manager',
                        auth=(cloudID, installCode))

                    if r.status_code == 401:
                        error = True
                        errorsDict['cloudID'] = u"Please verify CloudID."
                        errorsDict['installCode'] = u"Please verify Install Code."
                        errorsDict['showAlertText'] += "Please verify CloudID and Install Code"
                        self.debugLog(u"Request Status Code: %s" % r.status_code)

            # If there are errors, return them.
            if error:
                # Strip the newlines off the end of the dialog text.
                errorsDict['showAlertText'] = errorsDict['showAlertText'].strip()
                return (False, valuesDict, errorsDict)

        return (True, valuesDict)

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        """Plugin Configuration Dialog Closed"""
        if not userCancelled:
            self.debug = valuesDict.get("showDebugInfo", False)
            if self.debug:
                indigo.server.log(u"Debug logging enabled")
            else:
                indigo.server.log(u"Debug logging disabled")


    def updateDeviceProps(self, device, newProps):
        """Update Device Properties if Changed"""
        if device.pluginProps != newProps:
            self.debugLog("updateDeviceProps: Updating device " + device.name + " properties.")
            device.replacePluginPropsOnServer(newProps)


    def updateDeviceState(self, device, state, newValue):
        """Update Device State"""
        self.debugLog(u"updateDeviceState called.")
        if (newValue != device.states[state]):
            # If this is a floating point number, specify the maximum
            #   number of digits to make visible in the state.  Everything
            #   in this plugin only needs 3 decimal place of precision.
            #   If this isn't a floating point value, don't specify a number
            #   of decimal places to display.
            if newValue.__class__.__name__ == 'float':
                device.updateStateOnServer(key=state, value=newValue, decimalPlaces=3)
            else:
                device.updateStateOnServer(key=state, value=newValue)

    def runConcurrentThread(self):
        """Run Background Work Thread"""
        self.debugLog(u"Starting runConcurrentThread.")
        # Set a loop counter.
        loops = 0
        try:
            while True:

                # Cycle through each EAGLE device to update it.
                for deviceId in self.deviceList:
                    # Call the update method with the device instance
                    device = indigo.devices[deviceId]
                    localProps = device.pluginProps
                    # Make sure there's a meterHardwareAddress address associated with the device.
                    if localProps.get('meterHardwareAddress', "") == "":
                        # Update the device info.
                        self.eagleDeviceInfo(device)
                    # Update everything, but only if a meterHardwareAddress exists in the device.
                    if localProps.get('meterHardwareAddress', "") != "":
                        # Update the device data every loop iteration.
                        self.eagleDeviceData(device)

                # Sleep 5 seconds before updating again.
                self.sleep(5)
        except self.StopThread:
            pass

    def createAndSendRequest(self, device, command):
        """Create the request to send to the Eagle"""
        cloudID = device.pluginProps.get('cloudID', "")
        installCode = device.pluginProps.get('installCode', "")
        ipAddress = device.pluginProps.get('ipAddress', "")

        t0 = time.time()
        s = requests.Session()
        s.auth = (cloudID, installCode)

        try:
            r = requestsRetrySession(session=s).post('http://' + ipAddress + \
                '/cgi-bin/post_manager', data=command, timeout=5)
        except Exception as err:
            self.debugLog(u"Failure requesting data from Eagle: %s" % err.__class__.__name__)
            r = None
        else:
            self.debugLog(u"Request Status Code: %s \n Request Response: %s" % \
                (r.status_code, r.text))
        finally:
            t1 = time.time()
            self.debugLog(u"Request completed: %s seconds" % str(t1 - t0))

        return r

    def sendCommand(self, device, command, filters=[]):
        """Send a command to EAGLE Device, Return Response"""

        # Send a command to an EAGLE device.
        self.debugLog(u"sendCommand called.")

        meterHardwareAddress = device.pluginProps.get('meterHardwareAddress', "")
        theXml = ""

        header = "<Command>\n"     # Command header.
        footer = "</Command>\n"    # Command footer.

        # Create the XML based on the command name.
        if command == "device_list":
            # List Devices query
            command = header + " <Name>" + command + "</Name>\n" + footer
        elif command == "device_query":
            # Get Device Data query
            command = header + " <Name>" + command + "</Name>\n<DeviceDetails>\n \
                <HardwareAddress>\n" + meterHardwareAddress + "</HardwareAddress>\n \
                </DeviceDetails>\n <Components>\n<All>Y</All>\n</Components>\n" \
                + footer

        self.debugLog(u"Sending command\n " + command + u"\n to \"%s\"." % (device.name))
        request = self.createAndSendRequest(device, command)

        if request is None:
            indigo.server.log(u"No response from EAGLE %s. Skipping device info \
                query." % device.pluginProps.get('ipAddress'))
            return request

        theXml = request.text

        # Clean up the XML.
        # Remove non-ascii characters.
        theXml = re.sub('[\x80-\xFF]', '', theXml)
        # Remove newlines as they often appear in the middle of tag names.
        theXml = re.sub('\n', '', theXml)

        # Return the data gathered.
        return theXml

    def eagleDeviceInfo(self, device):
        """Get Device Info from Eagle"""
        self.debugLog(u"eagleDeviceInfo called.  Device: %s" % (device.name))

        error = False

        localProps = device.pluginProps

        theCommand = "device_list"
        theXml = self.sendCommand(device, theCommand)

        if theXml is not None:
            xmlTree = objectify.fromstring(theXml)

            # From the possible list of devices found, select the device that is the electric meter
            for node in xmlTree.xpath('Device/ModelId[.="electric_meter"]/../HardwareAddress'):
                try:
                    localProps['meterHardwareAddress'] = node.text
                except Exception, e:
                    self.debugLog(u"Unable to get \"DeviceHardwareAddress\" XML \
                        element from EAGLE. Error was: " + str(e))
                    error = True

            # Update Device Properties on Server.
            self.updateDeviceProps(device, localProps)
        else:
            error = True

        # Display a generic error message if there were any errors.
        if error:
            indigo.server.log(u"The device list data returned from the EAGLE was \
            corrupt or incomplete. Enable debugging in the Energy EAGLE plugin \
            configuration to start viewing detailed error logs.")

    def eagleDeviceData(self, device):
        """Get Data from Eagle Device"""
        self.debugLog(u"eagleDeviceData called.  Device: %s" % (device.name))

        error = False

        localProps = device.pluginProps

        costPerHour = 0

        theCommand = "device_query"
        theXml = self.sendCommand(device, theCommand)

        if theXml is not None:
            xmlTree = objectify.fromstring(theXml)
            newRoot = xmlTree.Components.Component.Variables

            try:
                instantaneousDemand = newRoot.xpath('Variable/Name[.="zigbee:InstantaneousDemand"]/../Value')
                instantaneousDemand = str(instantaneousDemand[0])
            except Exception, e:
                self.errorLog(u"Unable to gather data from \"" + device.name + u"\". Error was: " + str(e))
                # Exit early.
                return False

            # Update Device Properties on Server.
            self.updateDeviceProps(device, localProps)

            # Price
            try:
                price = newRoot.xpath('Variable/Name[.="zigbee:Price"]/../Value')
                price = float(price[0])
            except Exception, e:
                price = 0
            # Trailing Digits
            try:
                exponent = newRoot.xpath('Variable/Name[.="zigbee:TrailingDigits"]/../Value')
                exponent = int(exponent[0])
            except Exception, e:
                exponent = 1
            # Tier
            try:
                tier = newRoot.xpath('Variable/Name[.="zigbee:PriceTier"]/../Value')
                tier = int(tier[0])
            except Exception, e:
                tier = 0
            # Rate Label
            try:
                rateLabel = newRoot.xpath('Variable/Name[.="zigbee:RateLabel"]/../Value')
                rateLabel = str(rateLabel[0])
            except Exception, e:
                rateLabel = ""
            if rateLabel != None:
                rateLabel = rateLabel
            else:
                rateLabel = ""

            # Update the device states.
            self.updateDeviceState(device, 'instantaneousDemand', instantaneousDemand)
            self.updateDeviceState(device, 'price', price)
            self.updateDeviceState(device, 'tier', tier)
            self.updateDeviceState(device, 'rateLabel', rateLabel)

            # Instantaneous Demand (kW)...
            energyInput1 = instantaneousDemand
            energyInput1 = re.sub(r' kW', '', energyInput1)
            multiplier = newRoot.xpath('Variable/Name[.="zigbee:Multiplier"]/../Value')[0]
            try:
                divisor = newRoot.xpath('Variable/Name[.="zigbee:Divisor"]/../Value')[0]
            except Exception, e:
                divisor = 1        # Prevent divide-by-zero
            # Detect if instantaneous demand is positive or negative.
            energyInput1 = float(energyInput1) * float(multiplier) / float(divisor)
            #   Calculate Delta Amount...
            energyInput1Delta = float(energyInput1) - float(device.states['energyInput1'])
            #   Calculate Cost Per Hour...
            costPerHour = energyInput1 * float(price)
            #   Now update the energyInput1 and costPerHour states.
            self.updateDeviceState(device, 'energyInput1', energyInput1)
            self.updateDeviceState(device, 'costPerHour', costPerHour)
        else:
            error = True
            self.debugLog(u"No data returned from request. No device data to process.")
