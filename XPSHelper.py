####################################################################
# IMPORTS
####################################################################
import os
from newportxps import NewportXPS
import math
import csv
import numpy as np

####################################################################
# UNIT FUNCTIONS
####################################################################

def ConvertPsToMm(ps, zeroOffset, passes, reverse):
	c = 0.3 # Speed of light in mm/ps

	if reverse:
		return (-1 * c * (1 / passes) * (ps + zeroOffset)) 
	else:
		return (c * (1 / passes) * (ps + zeroOffset))

def ConvertMmToPs(mm, zeroOffset, passes, reverse):
	c = 0.3 # Speed of light in mm/ps

	if reverse:
		return ((mm * passes) / -c) - zeroOffset
	else:
		return ((mm  * passes) / c) - zeroOffset

def GetBandwidthStageSpeed(bandwidth, tc, tcToWait, passes):
	# This code is taken from Josh's THz scan program
	minSamplingPeriod = 1 / (bandwidth * 2) # ps
	maxStageSpeed = minSamplingPeriod / (tc * tcToWait) # ps/s
	
	return maxStageSpeed * 0.3 * (1 / passes) # mm/s

####################################################################
# GENERAL FUNCTIONS
####################################################################

def InitXPS(ip, user = "Administrator", password = "Administrator"):
	# 'known_hosts' filepath
	kfFilepath = "{}\\.ssh\\known_hosts.".format(os.path.expanduser('~'))

	# Check if the 'known_hosts' file exists
	if not os.path.exists(kfFilepath):
		# Gets the ssh keys from the xps and store to 'known_hosts'
		os.system("ssh-keyscan {} > {}".format(ip, kfFilepath))

	# Connects to the XPS and creates an object
	xps = NewportXPS(ip, username=user, password=password)

	return xps

def GotoDelay(xps, stage, delay, zeroOffset, passes, reverse):
	# Get max velocity settings
	maxVeloAcc = xps._xps.PositionerMaximumVelocityAndAccelerationGet(xps._sid, stage)

	# Set velocity to max
	err, msg = xps._xps.PositionerSGammaParametersSet(xps._sid, stage, maxVeloAcc[1], maxVeloAcc[2], 0.005, 0.05)

	# Check for errors
	if err != 0:
		return err, msg

	# Move stage to start pos
	xps.move_stage(stage, ConvertPsToMm(delay, zeroOffset, passes, reverse))

	return err, msg

####################################################################
# GATHERING FUNCTIONS
####################################################################

def GetGatheringFile(xps, localFile = None):
	# Delete existing gathering file
	if localFile == None:
		localFile = 'Gathering.dat'
	
	if os.path.exists(localFile):
		os.remove(localFile)

	xps.ftpconn.connect()

	xps.ftpconn._conn.get('/Admin/Public/Gathering/Gathering.dat', localFile)

	xps.ftpconn.close()


def InitXPSGathering(xps, stage, startDelay, stepDelay, stopDelay, zeroOffset, passes, reverse, bandwidth, tc, tcToWait = 4, extraGPIO = True):
	scanStageSpeed = GetBandwidthStageSpeed(bandwidth, tc, tcToWait, passes) # mm/s
	scanSteps = ConvertPsToMm(stepDelay, 0, passes, False) # mm
	scanPeriod = scanSteps / scanStageSpeed # s

	expectedPoints = int(math.floor(((stopDelay - startDelay) / stepDelay) + 2))
	xpsDivisor = int(math.floor(scanPeriod * 10000))

	# Kill Any Gathering Currently Running
	err, msg = xps._xps.GatheringStop(xps._sid)

	# Check for errors
	if err != 0:
		return err, msg
	
	err, msg = xps._xps.GatheringReset(xps._sid)

	# Check for errors
	if err != 0:
		return err, msg

	# Get max velocity settings
	maxVeloAcc = xps._xps.PositionerMaximumVelocityAndAccelerationGet(xps._sid, stage)

	# Set velocity to max
	err, msg = xps._xps.PositionerSGammaParametersSet(xps._sid, stage, maxVeloAcc[1], maxVeloAcc[2], 0.005, 0.05)

	# Check for errors
	if err != 0:
		return err, msg

	# Move stage to start pos
	xps.move_stage(stage, ConvertPsToMm(startDelay, zeroOffset, passes, reverse))

	# Set stage velocity based on required THz bandwidth
	err, msg = xps._xps.PositionerSGammaParametersSet(xps._sid, stage, scanStageSpeed, maxVeloAcc[2], 0.005, 0.05)

	# Check for errors
	if err != 0:
		return err, msg


	# Kill Any Gathering Currently Running
	err, msg = xps._xps.GatheringStop(xps._sid)

	# Check for errors
	if err != 0:
		return err, msg
	
	err, msg = xps._xps.GatheringReset(xps._sid)

	# Check for errors
	if err != 0:
		return err, msg

	# Set gathering config
	if extraGPIO:
		err, msg = xps._xps.GatheringConfigurationSet(xps._sid, ["{}.CurrentPosition".format(stage), "GPIO4.ADC1", "GPIO4.ADC2", "GPIO4.ADC3"])
	else :
		err, msg = xps._xps.GatheringConfigurationSet(xps._sid, ["{}.CurrentPosition".format(stage), "GPIO4.ADC1", "GPIO4.ADC2"])

	# Check for errors
	if err != 0:
		return err, msg

	# Set event trigger
	err, msg = xps._xps.EventExtendedConfigurationTriggerSet(xps._sid, ("{}.SGamma.MotionStart".format(stage),), ("",), ("",), ("",), ("",))

	# Check for errors
	if err != 0:
		return err, msg

	# Set event action
	err, msg = xps._xps.EventExtendedConfigurationActionSet(xps._sid, ("GatheringRun",), (str(expectedPoints),), (str(xpsDivisor),), ("",), ("",))

	# Check for errors
	if err != 0:
		return err, msg

	# Event ext. Start
	err, msg = xps._xps.EventExtendedStart(xps._sid)

	# Check for errors
	return err, msg
	

def RunGathering(xps, stage, startDelay, stepDelay, stopDelay, zeroOffset, passes, reverse, localFile = None):
	# Move to end position
	xps.move_stage(stage, ConvertPsToMm(stopDelay, zeroOffset, passes, reverse))

	# Gathering stop + save
	err, msg = xps._xps.GatheringStopAndSave(xps._sid)

	# Check for errors
	if err != 0:
		return err, msg

	# Get gathering file
	GetGatheringFile(xps, localFile)

	return err, msg
	
def ReadGathering(startDelay, stepDelay, stopDelay, zeroOffset, passes, reverse, lockinSensitivity, localFile = None, headerLines = 2, extraGPIO = True):
	if localFile == None:
		localFile = "Gathering.dat"
	
	# Empty variables to store gathering data to
	delay = []
	sigX = []
	sigY = []
	sigMon = []

	# Open gathering file
	with open(localFile, mode='r') as dataFile:
		dataReader = csv.reader(dataFile, delimiter='\t')

		# Skip header lines
		for i in range(headerLines):
			next(dataReader, None)

		# Read file row-by-row
		for row in dataReader:
			# Store data to variables
			delay.append(ConvertMmToPs(float(row[0]), zeroOffset, passes, reverse))
			sigX.append(float(row[1]) * lockinSensitivity * 0.1)
			sigY.append(float(row[2]) * lockinSensitivity * 0.1)

			if extraGPIO:
				sigMon.append(float(row[3]))

	# Interpolate data
	delayInterp = np.arange(startDelay, stopDelay + stepDelay, stepDelay)
	xInterp = np.interp(delayInterp, delay, sigX)
	yInterp = np.interp(delayInterp, delay, sigY)

	if extraGPIO:
		return {"Delay": delayInterp, "X": xInterp, "Y": yInterp, "SigMon": sigMon}
	else:
		return {"Delay": delayInterp, "X": xInterp, "Y": yInterp}

def GetXPSErrorString(xps, errorCode):
	# Check for errors
	if errorCode != 0:
		# Get XPS error string
		_, errString = xps._xps.ErrorStringGet(xps._sid, errorCode)

		return errString
	else:
		return "No XPS Error"

