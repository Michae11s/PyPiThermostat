#####################################################
# Created by Kyle Michaels                          #
# python code to control a thermostat via a relay   #
# i2c temperature sensor                            #
# mqtt messaging                                    #
#####################################################\

#IMPORTS
import sys
import paho.mqtt.client as mqtt
import time
import os
from datetime import datetime as dt
import board
import busio
import adafruit_si7021 as asi
import digitalio as di
import adafruit_character_lcd.character_lcd as char_lcd

###
#Print to file instead of terminal
###

class Logger(object):
    def __init__(self, filename="Default.log"):
        self.terminal = sys.stdout
        self.log = open(filename, "a")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

sys.stdout = Logger("/home/pi/build/PyPiThermostat/py.log")

class Schedule(object):
    def __init__(self, filename="schedule.csv"):
        self.filename=filename
        self.sun = []
        self.mon = []
        self.tues = []
        self.wed = []
        self.thurs = []
        self.fri = []
        self.sat = []
        self.wait = 26
        self.imprt()

    def imprt(self):
        if(os.path.exists(self.filename)):
            #Import the file
            SF=open(self.filename, "r")
            for splits in SF.readlines():
                splitd=splits.split(",")
                if(splitd[1] != "Sun"):
                    self.sun.append(splitd[1])
                    self.mon.append(splitd[2])
                    self.tues.append(splitd[3])
                    self.wed.append(splitd[4])
                    self.thurs.append(splitd[5])
                    self.fri.append(splitd[6])
                    self.sat.append(splitd[7])
        else:
            print("error schedule file not found")

    def schTemp(self):
        Hr=int(dt.now().strftime("%H"))
        weekDay=dt.today().weekday()
        if(weekDay == 0):
            return(self.mon[Hr])
        elif(weekDay == 1):
            return(self.tues[Hr])
        elif(weekDay == 2):
            return(self.wed[Hr])
        elif(weekDay == 3):
            return(self.thurs[Hr])
        elif(weekDay == 4):
            return(self.fri[Hr])
        elif(weekDay == 5):
            return(self.sat[Hr])
        elif(weekDay == 6):
            return(self.sun[Hr])

    def setWait(self):
        Hr=int(dt.now().strftime("%H"))
        if(Hr == 22):
            self.wait=00
        elif(Hr == 23):
            self.wait=01
        else:
            self.wait=Hr+2

    def clrWait(self):
        self.wait=26

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
minON=60
minOFF=60

#amount of time between samples in seconds
PollingRate=15

ThermI2Caddr=0xFF

###############
# global vars #
###############
logFile='/home/pi/build/PyPiThermostat/sensor.log'
scheduleFile='/home/pi/build/PyPiThermostat/schedule.csv'

#schedule variables
shed = Schedule(scheduleFile)
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
    hum=round(sensor.relative_humidity, 1)
    #print('temperature is: ' + str(temp) + ', and humidity is: ' + str(hum))
    #print('Humidity: {}%'.format(sensor.relative_humidity))
    #time.sleep(1)
    LF=open(logFile,"a")
    tim=int(dt.now().strftime("%H%M%S"))
    LF.write(str(tim)+","+str(temp)+","+str(hum)+"\n")
    LF.close()


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
            relay.value=True
            OnTime=timenow
            mqc.publish(preamb+"heaton",heaton,0,True)
            lastheaton=heaton
            print("we did! heat is now: " + str(heaton))
        if((heaton=="OFF") and (timenow > OnTime+minON)):
            ###*** Turn heat off here ***##
            relay.value=False
            OffTime=timenow
            mqc.publish(preamb+"heaton",heaton,0,True)
            lastheaton=heaton
            print("we did! heat is now: " + str(heaton))

# funtion to change the setpoint based on a schedule
def scheduleAdjust():
    Hr=int(dt.now().strftime("%H"))
    global setpoint
    if(shed.wait != 26): #make sure we aren't waiting
        new=shed.schTemp()
        if(new != setpoint): #check for a change
            setpoint=new
            mqc.publish(preamb+"setpoint",setpoint,0,True)
    elif(Hr == shed.wait):#we must be waiting, check if we are done
        shed.clrWait()


def displayUpdate():
    tim=dt.now().strftime("%H:%M")
    screen_home= str(tim) + " Set:" + str(setpoint) +"\x00F\n" + str(temp) + "\x00F H:" + str(hum) + "%"
    lcd.clear()
    lcd.message=screen_home

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
                shed.setWait()
                print("new setpoint:" + str(setpoint))
            else:
                mqc.publish(preamb+"setpoint",setpoint,0,True)
                print("attempted to set a heating value out of bounds, pushing back")
    elif(msg.topic == (preamb + "mode")):
        nmode=str(pay)
        if(nmode=="off" or nmode=="heat" or nmode=="eco"):
            mode=nmode
            print("new mode: " + mode)
    # elif(msg.topic == (preamb + "schedule")):
    #     schedule=str(pay)
    #     lines=schedule.split(";")
    #     SF=open(scheduleFile, "w")
    #     SF.writelines(lines)
    #     SF.close()
    #
    #     #add lines to the scizm var
    #     scizm.clear()
    #     for line in lines:
    #         splitd=line.split(":")
    #         scizm.append(list(map(int,splitd)))


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

#16x2 char lcd setup
lcd_rs = di.DigitalInOut(board.D25)
lcd_en = di.DigitalInOut(board.D24)
lcd_d7 = di.DigitalInOut(board.D22)
lcd_d6 = di.DigitalInOut(board.D18)
lcd_d5 = di.DigitalInOut(board.D17)
lcd_d4 = di.DigitalInOut(board.D23)
lcd_backlight = di.DigitalInOut(board.D27)

lcd_columns = 16
lcd_rows = 2

lcd = char_lcd.Character_LCD_Mono(lcd_rs, lcd_en, lcd_d4, lcd_d5, lcd_d6, lcd_d7, lcd_columns, lcd_rows, lcd_backlight)
lcd.clear()
lcd.message = "Starting...\nThermostat " + str(DeviceNum)
lcd.backlight = True
lcd.cursor = False

#create degree symbol
deg = bytes([0x2, 0x5, 0x2, 0x0, 0x0, 0x0, 0x0, 0x0])
#deg = bytes([0x4, 0xa, 0x4, 0x0, 0x0, 0x0, 0x0, 0x0])
# Store in LCD character memory 0
lcd.create_char(0, deg)

#Create gpio pins
#relay pin
relay= di.DigitalInOut(board.D26)
relay.direction = di.Direction.OUTPUT

#up button
btnUp=di.DigitalInOut(board.D6)
btnUp.direction = di.Direction.INPUT
btnUp.pull = di.Pull.UP

#sel button
btnSel=di.DigitalInOut(board.D13)
btnSel.direction = di.Direction.INPUT
btnSel.pull = di.Pull.UP

#down button
btnDn=di.DigitalInOut(board.D19)
btnDn.direction = di.Direction.INPUT
btnDn.pull = di.Pull.UP

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

        displayUpdate()

#mqc.loop_stop()
mqc.disconnect()
