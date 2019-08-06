#####################################################
# Created by Kyle Michaels                          #
# python code to control a thermostat via a relay   #
# i2c temperature sensor                            #
# mqtt messaging                                    #
#####################################################\

#IMPORTS
import paho.mqtt.client as mqtt
import time
import os
from datetime import datetime as dt
import board
import busio
import adafruit_si7021 as asi

####
#CONFIGURATION VARS
####
DeviceNum=1
MQTTservAddr="192.168.1.1"
MQTTport=1883
MQTTuser="openhab"
MQTTpass="michaels"

#setpoint min and max temperatures
setMin=45
setMax=85

#eco here is used to increase temp range before turning on boiler
ecoRange=5

ThermostatRange=1.0 #max distance temp can be below setpoint before heat kicks on

#min on off times seconds
minON=5
minOFF=5

#amount of time between samples in seconds
PollingRate=15

ThermI2Caddr=0xFF

###############
# global vars #
###############
logFile='sensor.log'
scheduleFile='.schedule'

#schedule variables
scizm=[]

preamb="/home/thermostats/" + str(DeviceNum) + "/"

OnTime=0
OffTime=0

setpoint=70.0
mode="heat"
temp=0.0
hum=0
heaton="null"

lastTime=0
lasttemp=0.0
lasthum=0
lastheaton="null"


###
# misc functions
###

# polling function to update humidity and temp and publish
def pole():
    global temp
    global hum
    global lasttemp
    global lasthum

    tempC=sensor.temperature
    tempf=9.0/5.0*tempC+32.0
    temp=round(tempf,1)
    humidity=round(sensor.relative_humidity, 1)
    #print('Temperature: {} degrees C'.format(sensor.temperature))
    #print('Humidity: {}%'.format(sensor.relative_humidity))
    #time.sleep(1)

    if(hum != lasthum):
        lasthum=hum
        mqc.publish(str(preamb + "hum"),hum,0,True)
        print("humidity set to: " + str(hum))
    if(temp != lasttemp):
        lasttemp=temp
        mqc.publish(str(preamb + "temperature"),temp,0,True)
        print("temperature set to: " + str(temp))

# function turn on or off heating as appropriate
def heatActiv():
    global lastheaton
    global heaton
    global OnTime
    global OffTime

    #check our modes then make appropriate decisions
    if(mode=="off"):
        #never turn the heater on
        heaton="OFF"
    elif(mode=="heat"):
        #determine if we need heat then act appropriately
        if(temp >= setpoint): #too hot turn off
            heaton="OFF"
        elif(setpoint - ThermostatRange >= temp):
            heaton="ON"
    elif(mode=="eco"):
        if(temp >= setpoint): #too hot turn off
            heaton="OFF"
        elif(setpoint - ecoRange >= temp):
            heaton="ON"

    if(lastheaton!=heaton):
        print("we want to toggle the heaters")
        timenow=time.time()
        if((heaton=="ON") and (timenow > OffTime+minOFF)):
            ##*** Turn heat on here ***##
            OnTime=timenow
            mqc.publish(preamb+"heaton",heaton,0,True)
            lastheaton=heaton
            print("we did! heat is now: " + str(heaton))
        if((heaton=="OFF") and (timenow > OnTime+minON)):
            ###*** Turn heat off here ***##
            OffTime=timenow
            mqc.publish(preamb+"heaton",heaton,0,True)
            lastheaton=heaton
            print("we did! heat is now: " + str(heaton))

# funtion to change the setpoint based on a schedule
def scheduleAdjust():
    global setpoint
    for splitz in scizm:
        cdt=dt.now()
        tim=int(cdt.strftime("%H%M"))
        if(splitz[0] == tim):
            setpoint=splitz[2]
            mqc.publish(preamb+"setpoint",setpoint,0,True)

def scheduleImport():
    #incase we can't connect to the broker still want to run the last known schedule
    global scizm
    global setpoint
    global endTime

    if(os.path.exists(scheduleFile)):
        #Import the file
        SF=open(scheduleFile, "r")
        for splits in SF.readlines():
            splitd=splits.split(":")
            scizm.append(list(map(int,splitd)))

        for splitz in scizm:
            cdt=dt.now()
            tim=int(cdt.strftime("%H%M"))
            if(splitz[0] <= tim and tim <= splitz[1]):
                setpoint=splitz[2]
                mqc.publish(preamb+"setpoint",setpoint,0,True)

###
# MQTT functions
###

def on_connect(client, userdata, flags, rc):
    print("connected to mqtt: " + str(rc))

    #subsribe on the connect in order to refresh if the client disconnects and reconnect
    #mqc.subsribe(preamb + "temperature")
    mqc.subscribe(preamb + "setpoint")
    mqc.subscribe(preamb + "mode")
    #mqc.subsribe(preamb + "hum")
    #mqc.subsribe(preamb + "heaton")
    mqc.subscribe(preamb + "schedule")

def on_message(client, userdata, msg):
    global setpoint
    global mode
    global scizm
    print("topic updated:" + str(msg.topic) + ":" + str(msg.payload))
    pay=msg.payload.decode("utf-8")

    if(msg.topic == (preamb + "setpoint")):
        if(pay.isdigit()):
            set=int(pay)
            if(setMax >= set and set >= setMin):
                setpoint=set
                print("new setpoint:" + str(setpoint))
            else:
                mqc.publish(preamb+"setpoint",setpoint,0,True)
                print("attempted to set a heating value out of bounds, pushing back")
    elif(msg.topic == (preamb + "mode")):
        nmode=str(pay)
        if(nmode=="off" or nmode=="heat" or nmode=="eco"):
            mode=nmode
            print("new mode: " + mode)
    elif(msg.topic == (preamb + "schedule")):
        schedule=str(pay)
        lines=schedule.split(";")
        SF=open(scheduleFile, "w")
        SF.writelines(lines)
        SF.close()

        #add lines to the scizm var
        scizm.clear()
        for line in lines:
            splitd=line.split(":")
            scizm.append(list(map(int,splitd)))

###
# setup code
###
# mqtt setup
mqc = mqtt.Client()

mqc.on_connect = on_connect
mqc.on_message = on_message

mqc.username_pw_set(MQTTuser, password=MQTTpass)
mqc.connect(MQTTservAddr,MQTTport)

# not the primary method just used as a reserve incase the broker is down
scheduleImport()

# i2c setup
i2c=busio.I2C(board.SCL, board.SDA)
sensor=asi.SI7021(i2c)

#start the infinte loop
#mqc.loop_start()
while True:
    mqc.loop(timeout=1.0, max_packets=6)
    #determine if we need to re pole
    if ((time.time()-lastTime) > PollingRate):
        lastTime=time.time()
        pole() #update temp and humidity

        #check if we need to turn on the heater
        heatActiv()

        scheduleAdjust()

#mqc.loop_stop()
mqc.disconnect()
