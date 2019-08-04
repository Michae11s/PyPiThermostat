#####################################################
# Created by Kyle Michaels                          #
# python code to control a thermostat via a relay   #
# i2c temperature sensor                            #
# mqtt messaging                                    #
#####################################################\

#IMPORTS
import paho.mqtt.client as mqtt
import time

####
#CONFIGURATION VARS
####
DeviceNum=1
MQTTservAddr="localhost"
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

###
# global vars
###

preamb="null"

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

    ###DO SOME SHIT WITH I2C to fetch the humidity until then lets lie

    temp=75.5
    hum=85.5
    if(hum != lasthum):
        lasthum=hum
        mqc.publish(str(preamb + "hum"),hum,0,True)
    if(temp != lasttemp):
        lasttemp=temp
        mqc.publish(str(preamb + "temperature"),temp,0,True)

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
    setpoint=setpoint

###
# MQTT setup
###

def on_connect(client, userdata, flags, rc):
    print("connected to mqtt: " + str(rc))
    global preamb

    #subsribe on the connect in order to refresh if the client disconnects and reconnects
    preamb="/home/thermostats/" + str(DeviceNum) + "/"
    #mqc.subsribe(preamb + "temperature")
    mqc.subscribe(preamb + "setpoint")
    mqc.subscribe(preamb + "mode")
    #mqc.subsribe(preamb + "hum")
    #mqc.subsribe(preamb + "heaton")
    mqc.subscribe(preamb + "schedule")

def on_message(client, userdata, msg):
    global setpoint
    global mode
    print("topic updated:" + str(msg.topic) + ":" + str(msg.payload))
    pay=msg.payload.decode("utf-8")

    if(msg.topic == (preamb + "setpoint")):
        if(pay.isdigit()):
            set=int(pay)
            if(setMax >= set and set >= setMin):
                setpoint=set
                print("new setpoint:" + str(setpoint))
    elif(msg.topic == (preamb + "mode")):
        nmode=str(pay)
        if(nmode=="off" or nmode=="heat" or nmode=="eco"):
            mode=nmode
            print("new mode: " + mode)
    elif(msg.topic == (preamb + "schedule")):
        schedule="null"
        ###TRY TO PROCESS THE SCHEDULE

mqc = mqtt.Client()

mqc.on_connect = on_connect
mqc.on_message = on_message

mqc.username_pw_set(MQTTuser, password=MQTTpass)
mqc.connect(MQTTservAddr,MQTTport)

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
