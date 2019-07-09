from quart import Quart,request, render_template, redirect, url_for, jsonify
import asyncio
import RPi.GPIO  as GPIO
import time as tim
from datetime import datetime,time
import sqlite3 as lite
import sys


#******************** установка метрики ножек RPi
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)


#******************** класс датчика температуры
class DS1620:
    # ***************************************************************************************************
    # Настройка пинов, к которым подключён датчик DS1620.                                               *
    # ***************************************************************************************************
    def __init__(self, rst, dq, clk):
        """ DS1620 sensor constructor.
        Keyword arguments:
        rst -- Integer corresponding to the RST GPIO Pin.
        dq  -- Integer DAT/DQ GPIO Pin.
        clk -- Integer CLK GPIO Pin.
        """

        GPIO.setmode(GPIO.BCM)  # Set the mode to get pins by GPIO #
        self._rst = rst
        self._dq = dq
        self._clk = clk

    # ***************************************************************************************************
    # Отправка команды датчику.                                                                         *
    # ***************************************************************************************************
    def __send_command(self, command):
        """ Sends an 8-bit command to the DS1620 """

        for n in range(0, 8):
            bit = ((command >> n) & (0x01))
            GPIO.output(self._dq, GPIO.HIGH if (bit == 1) else GPIO.LOW)
            GPIO.output(self._clk, GPIO.LOW)
            GPIO.output(self._clk, GPIO.HIGH)

    # ***************************************************************************************************
    # Чтение ответа с датчика.                                                                          *
    # ***************************************************************************************************
    def __read_data(self):
        """ Read 8 bit data from the DS1620 """

        raw_data = 0  # Go into input mode.
        for n in range(0, 9):
            GPIO.output(self._clk, GPIO.LOW)
            GPIO.setup(self._dq, GPIO.IN)
            if GPIO.input(self._dq) == GPIO.HIGH:
                bit = 1
            else:
                bit = 0
            GPIO.setup(self._dq, GPIO.OUT)
            GPIO.output(self._clk, GPIO.HIGH)
            raw_data = raw_data | (bit << n)
        return raw_data

    # ***************************************************************************************************
    # Чтение текущей температуры с датчика.                                                             *
    # ***************************************************************************************************
    def get_temperature(self):
        """ Send the commands to retrieve the temperature in Celsuis """

        # Prepare the pins for output.
        GPIO.setup(self._rst, GPIO.OUT)
        GPIO.setup(self._dq, GPIO.OUT)
        GPIO.setup(self._clk, GPIO.OUT)

        GPIO.output(self._rst, GPIO.LOW)
        GPIO.output(self._clk, GPIO.HIGH)
        GPIO.output(self._rst, GPIO.HIGH)
        self.__send_command(0x0c)  # Write config command.
        self.__send_command(0x02)  # CPU Mode.
        GPIO.output(self._rst, GPIO.LOW)
        tim.sleep(0.2)  # Wait until the config register is written.
        GPIO.output(self._clk, GPIO.HIGH)
        GPIO.output(self._rst, GPIO.HIGH)
        self.__send_command(0xEE)  # Start conversion.
        GPIO.output(self._rst, GPIO.LOW)
        tim.sleep(0.2)
        GPIO.output(self._clk, GPIO.HIGH)
        GPIO.output(self._rst, GPIO.HIGH)
        self.__send_command(0xAA)
        raw_data = self.__read_data()
        GPIO.output(self._rst, GPIO.LOW)

        return raw_data / 2.0

#******************** инициализация пинов датчика
t_sensor = DS1620(23, 18, 24)
control = 17

#********************  вкл чайника
async def On():
    t=t_sensor.get_temperature()
    a = read_db("2")
    if t<a:
        GPIO.setup(control, GPIO.OUT, initial=GPIO.HIGH)
        return 1
    else:
        GPIO.setup(control, GPIO.OUT, initial=GPIO.LOW)
        return 0 
        
async def Check():
    h1 = read_db("3")
    m1 = read_db("4")
    h2 = read_db("5")
    m2 = read_db("6")
    if h1==h2:
        if m1==m2:
            update_db(1,"7")

#******************** Database
def init_db(b):
    db = lite.connect('test.db')
    cursor = db.cursor()
    cursor.execute("DROP TABLE IF EXISTS TEMP")    
    cursor.execute("CREATE table TEMP (Temp_id text,Temp_val int)")
    cursor.execute("INSERT INTO TEMP VALUES (?,?)",(1,t_sensor.get_temperature()))
    db.commit()
    cursor.execute("INSERT INTO TEMP VALUES (?,?)",(2,b))
    db.commit()
    e=datetime.now()
    if e.minute >= 10:
        cursor.execute("INSERT INTO TEMP VALUES (?,?)",(3,str(e.hour)))
        db.commit()
        cursor.execute("INSERT INTO TEMP VALUES (?,?)",(4,str(e.minute)))
        db.commit()
        cursor.execute("INSERT INTO TEMP VALUES (?,?)",(5,str(e.hour)))
        db.commit()
        cursor.execute("INSERT INTO TEMP VALUES (?,?)",(6,str(e.minute)))
        db.commit()
    else:
        cursor.execute("INSERT INTO TEMP VALUES (?,?)",(3,str(e.hour)))
        db.commit()
        cursor.execute("INSERT INTO TEMP VALUES (?,?)",(4,"0"+str(e.minute)))
        db.commit()
        cursor.execute("INSERT INTO TEMP VALUES (?,?)",(5,str(e.hour)))
        db.commit()
        cursor.execute("INSERT INTO TEMP VALUES (?,?)",(6,"0"+str(e.minute)))
        db.commit()
    cursor.execute("INSERT INTO TEMP VALUES (?,?)",(7,0))
    db.commit()
    db.close()
    
def update_db(a,b):
    db = lite.connect("test.db")
    cursor = db.cursor()
    cursor.execute("UPDATE TEMP SET Temp_val = ? WHERE Temp_id = ?",(a,b))
    db.commit()
    temp1=cursor.fetchone()
    db.close()
    
def read_db(a):
    db = lite.connect("test.db")
    cursor = db.cursor()
    cursor.execute("SELECT Temp_val FROM TEMP WHERE Temp_id = (?)",(a))
    temp=cursor.fetchone()
    db.close()
    return temp[0]

#******************** инициализация приложения
app = Quart(__name__)
init_db(100)

@app.route('/')
async def page():
     return """
    <!DOCTYPE html>
    <html lang="ru">
	<head>
    <meta charset="utf-8">
    <title>Temperature of teapot</title>
    </head>
    <body>
    <body>
		<center>
		<h1>
				Welcome to start page. You can select 1 of this methods:
		</h1>
        <a href="page1">To start now</a>
        <a href="page2">To start by time</a>
        </center>
    </body>
    </html>
    """   


#******************************************************************************************
#******************** Страница для установки температуры онли
#******************************************************************************************
@app.route('/page1', methods = ['POST'])
async def page1_create():
     form = (await request.form)
     if int(form['temp1'])>=20:
         if int(form['temp1'])<=100:
            update_db(form['temp1'],"2")
         else: 
            update_db(100,"2")
     else: 
         update_db(100,"2")
     return redirect(url_for('page1'))

#********************  Метод-ссылка  подачи страницы
@app.route('/page1')
async def page1():
     return """
    <!DOCTYPE html>
    <html lang="ru">
	<head>
    <meta charset="utf-8">
    <title>Temperature of teapot</title>
    <link rel="stylesheet" href="//code.jquery.com/ui/1.12.1/themes/base/jquery-ui.css">
    <link rel="stylesheet" href="/resources/demos/style.css">
    <script src="https://code.jquery.com/jquery-1.12.4.js"></script>
    <script src="https://code.jquery.com/ui/1.12.1./jquery-ui.js"></script>
    <script>
    var state;
    
    function checkStatus()
    {
        $.getJSON('""" + url_for('check_status1') + """',function (data)
        {
            console.log(data);
            if (parseFloat(data.state)==1)
            {
                state = "On";
            }
            else
            {
                state="Off";
            }
            temp = parseFloat(data.temp);
            temp1 = parseFloat(data.temp1);
            update_text(state);
            update_text(temp);
        });
        setTimeout(checkStatus,2000)
    }
    
    function update_text(val)
    {
        document.getElementById("temp").innerHTML = temp+"&#8451;";
        document.getElementById("temp1").innerHTML = temp1+"&#8451;";
        document.getElementById("state").innerHTML = state;
    }
    checkStatus();
    </script>
    </head?
    <body>
    <body>
		<center>
		<h1>
				Temperature of teapot now:
                <lable id="temp" name="temp"></lable>
		</h1>
        
        <h1>
				Temperature of teapot at last moment:<lable id="temp1" name="temp1"></lable></h1>
        
        <h1>
				State: <lable id="state" name="state"></lable>
		</h1>
        
        <form action=' """+url_for('page1_create') +"""' method="post">
			<label for="temp1">Temperature of teapot at you moment:</label>
			<input name="temp1" id="temp1" placeholder="Temp. of teapot" >
			<input type="submit" valuse="Send">
		</form>
        <a href="/">Back</a>
        </center>
    </body>
    </html>
    """   

#********************  Метод-ссылка  проверки статуса
@app.route('/check_status1/')
async def check_status1():
    status=dict()
    try:
        status['temp1']=read_db("2")
        update_db(t_sensor.get_temperature(),"1")
        status['temp']=read_db("1")
        if await On()==0:
            status['state']=0
        else:
            status['state']=1
    except:
        pass
    print(status)
    return jsonify(status)
    
#******************************************************************************************
#********************  Страница для установки температуры и времени
#******************************************************************************************
@app.route('/page2', methods = ['POST'])
async def page2_create():
     form = (await request.form)
     if int(form['temp1'])<=100:
         update_db(form['temp1'],"2")
     else:
         update_db(100,"2")
     update_db(form['hour'],"5")
     update_db(form['minute'],"6")
     update_db(0,"7")
     return redirect(url_for('page2'))

#********************  Метод-ссылка  подачи страницы
@app.route('/page2')
async def page2():
     return """
    <!DOCTYPE html>
    <html lang="ru">
	<head>
    <meta charset="utf-8">
    <title>Temperature of teapot</title>
    <link rel="stylesheet" href="//code.jquery.com/ui/1.12.1/themes/base/jquery-ui.css">
    <link rel="stylesheet" href="/resources/demos/style.css">
    <script src="https://code.jquery.com/jquery-1.12.4.js"></script>
    <script src="https://code.jquery.com/ui/1.12.1./jquery-ui.js"></script>
    <script>
    var state;
    
    function checkStatus()
    {
        $.getJSON('""" + url_for('check_status2') + """',function (data)
        {
            console.log(data);
            if (parseFloat(data.state)==1)
            {
                state = "On";
            }
            else
            {
                state="Off";
            }
            temp = parseFloat(data.temp);
            temp1 = parseFloat(data.temp1);
            time_now = String(parseFloat(data.time_now_h))+":"+String(parseFloat(data.time_now_m));
            time_start = String(parseFloat(data.time_start_h))+":"+String(parseFloat(data.time_start_m));
            update_text();
        });
        setTimeout(checkStatus,2000)
    }
    
    function update_text()
    {
        document.getElementById("temp").innerHTML = temp+"&#8451;";
        document.getElementById("temp1").innerHTML = temp1+"&#8451;";
        document.getElementById("time_now").innerHTML = time_now;
        document.getElementById("time_start").innerHTML = time_start;
        document.getElementById("state").innerHTML = state;
    }
    checkStatus();
    </script>
    </head>
    <body>
    <body>
		<center>
		<h1>
				Temperature of teapot now:
                <lable id="temp" name="temp"></lable>
		</h1>
        
        <h1>
				Temperature of teapot at last moment:<lable id="temp1" name="temp1"></lable></h1>
        <h1>
				Time now:<lable id="time_now" name="time_now"></lable></h1>
        <h1>
				Time start:<lable id="time_start" name="time_start"></lable></h1>
        <h1>
				State: <lable id="state" name="state"></lable>
		</h1>
        
        <form action=' """+url_for('page2_create') +"""' method="post">
			<label for="temp1">Temperature of teapot at you moment:</label>
			<input name="temp1" id="temp1" placeholder="Temp. of teapot" >
            <div><label for="hour">Hour you moment:</label>
			<input name="hour" id="hour" placeholder="Hour" >
            </div>
            <div><label for="time">Time you moment:</label>
			<input name="minute" id="minute" placeholder="Minutes" >
            </div>
			<input type="submit" valuse="Send">
		</form>
        <div>
        <a href="/">Back</a>
        </div>
        </center>
    </body>
    </html>
    """   

#********************  Метод-ссылка  проверки статуса
@app.route('/check_status2/')
async def check_status2():
    status=dict()
    try:
        status['temp1']=read_db("2")
        update_db(t_sensor.get_temperature(),"1")
        status['temp']=read_db("1")
        e=datetime.now()
        update_db(str(e.hour),"3")
        update_db(str(e.minute),"4")
        status['time_now_h']=read_db("3")
        status['time_now_m']=read_db("4")
        status['time_start_h']=read_db("5")
        status['time_start_m']=read_db("6")
        await Check()
        if read_db("7")==1:
            if await On()==0:
                status['state']=0
                update_db(0,"7")
            else:
                status['state']=1
        else:
            GPIO.setup(control, GPIO.OUT, initial=GPIO.LOW)
            status['state']=0
    except:
        pass
    print(status)
    return jsonify(status)
     
#******************** Запуск     
if __name__=="__main__":
    app.run()
