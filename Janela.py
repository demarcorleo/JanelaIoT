from machine import Pin, Timer, PWM
from time import sleep
from network import WLAN, STA_IF
import urequests as req
from dht import DHT11
from umqtt.simple import MQTTClient
from ustruct import pack

login = 'janelaauto21'
topico1 = "janela/sensor/TDHT"
topico2 = "janela/sensor/HDHT"
topico3 = "janela/sensor/TCT"
topico4 = "janela/sensor/HCT"
topico5 = "janela/sensor/PCT"
topico6 = "janela/estado"

broker = "broker.hivemq.com"
porta = 1883
rede='OsirMax_DeMarco'
senha='4014460780'
wifi = None


# Vão ser usados para acessar os dados meteorológicos periodicamente
tempSite   = Timer(0)
tempSensor = Timer(1)

# Pinos que acessam a ponte H
motorA  = Pin (26, Pin.OUT)
motorB  = Pin (25, Pin.OUT)
motorEn = Pin (14, Pin.OUT)
vel = PWM (Pin(13, Pin.OUT), freq=10000)

# Chaves fim de curso
fcAbre  = Pin (19, Pin.IN, Pin.PULL_DOWN)
fcFecha = Pin (18, Pin.IN, Pin.PULL_DOWN)

# Sensores meteorológicos
sensorChuva = Pin (2, Pin.IN, Pin.PULL_DOWN)
sensor = DHT11(Pin (27, Pin.IN))

def conectarMQTT(broker, login):
    
    cliente = MQTTClient(login, broker)
    cliente.connect()
    print ('Conectado a {}'.format(broker))
    return cliente
    

def paradaTotal(): # Faz o motor parar totalmente
    motorA.value(0)
    motorB.value(0)
    motorEn.value(0)


def abrirJanela(): # Movimenta o motor para abrir a janela
    motorEn.value(0)
    motorA.value(1)
    motorB.value(0)
    motorEn.value(1)
    vel.duty(900)


def fecharJanela(): # Movimenta o motor para fechar a janela
    motorEn.value(0)
    motorA.value(0)
    motorB.value(1)
    motorEn.value(1)
    vel.duty(900)


def conectar(rede, senha): # Estabele a conexão de rede
    global wifi
    
    wifi = WLAN(STA_IF)
    wifi.active(True)
    if not wifi.isconnected():
        print('Conectando a {}'.format(rede))
        wifi.connect(rede, senha)
        while not wifi.isconnected():
            pass
        print('Configuração de rede:', wifi.ifconfig())


def reconectar(rede, senha): # Verifica e reconecta se necessário - Parte da ideia de que foi usado o conecta
    global wifi
    
    if not wifi.isconnected():
        print('Reconectando a {}'.format(rede))
        wifi.connect(rede, senha)
        while not wifi.isconnected():
            pass
        print('Configuração de rede:', wifi.ifconfig())


climatempo = 'http://apiadvisor.climatempo.com.br/api/v1/weather/locale/5368/current?token=3553900326339507453cb505b6e4d14f'

def atualizaDoClimatempo(t):
    global horaDoClimatempo
    
    horaDoClimatempo = True


def atualizaDoDHT(t):
    global horaDoDHT
    
    horaDoDHT = True


def atualizaDHT(ambiente):
    
    print ('no DHT')
    
    try:
        sensor.measure()
        ambiente['chuva'] = sensorChuva.value()
        ambiente['upd'] = True
        ambiente['tDHT'] = sensor.temperature()
        ambiente['hDHT'] = sensor.humidity()
        payload1 = pack(">f", amb['tDHT'])
        payload2 = pack(">f", amb['hDHT'])
        cliente.publish(topico1, payload1)
        cliente.publish(topico2, payload2)
        cliente.publish(topico6, estadoJanela.encode())
    
    except:
        print("Problemas para comunicar com o DHT11")
        

def atualizaTempo(ambiente):
    reconectar (rede, senha)
    try:
        tempo = req.get(climatempo)
        
        if tempo.status_code == 200:
            t = tempo.json()
            ambiente['upd'] = True
            ambiente['tCT'] = t['data']['temperature']
            ambiente['pCT'] = t['data']['pressure']
            ambiente['hCT'] = t['data']['humidity']
    except:
        print ("Problemas para adquirir dados do Climatempo")
        

# Define o que fazer com base nas condições do ambiente
def verificaAmbiente():
    global amb
    global cmd
    if amb['upd']: # Houve atualização dos dados?
        print (estadoJanela)
        print (amb)
        
        payload3 = pack(">f", amb['tCT'])
        payload4 = pack(">f", amb['hCT'])
        payload5 = pack(">f", amb['pCT'])
        cliente.publish(topico3, payload3)
        cliente.publish(topico4, payload4)
        cliente.publish(topico5, payload5)
        cliente.publish(topico6, estadoJanela.encode())
        
        if estadoJanela not in ('fechado', 'fechando') and \
           (amb['chuva'] or amb['hDHT'] >= 80.0 or amb['hCT'] >= 80.0): # Chuva ou Umidade alta
            cmd = 'fechar'
            print ('deve fechar') 
        elif estadoJanela not in ('aberto', 'abrindo') and \
           not amb['chuva'] and (amb['tDHT'] >= 20 or amb['tCT'] >= 20) and (amb['hDHT'] < 80.0 or amb['hCT'] < 80.0):
            cmd = 'abrir'
            print ('deve abrir')
        else:
            print ('deve ficar como está')
        amb['upd'] = False # Já avaliou o novo ambiente e não precisa mais avaliar até as condições mudarem
         
###########################################################
# Inicio do script de fato. Antes disso, apenas preparação

conectar(rede, senha) # Conectando à rede
cliente = conectarMQTT (broker, login)

paradaTotal() # Forçando a janela a ficar parada na partida

amb = {'upd': False, 'tDHT': None, 'hDHT': None, 'chuva': False,
       'tCT': None, 'pCT': None, 'hCT': None}   # Relação de variáveis do ambiente da janela - vazia

horaDoClimatempo = False
horaDoDHT = False

estadoJanela = 'parado' # fechada, aberta, fechando, abrindo, parada

cmd = ''   # Define o comando que deve ser disparado pelo loop de vigilância

# Inicia a verificação periódica do climatempo e do sensor
tempSite.init(period=10000, mode=Timer.PERIODIC, callback=atualizaDoClimatempo) # 900000: 15 minutos(em ms)
tempSensor.init(period=10000, mode=Timer.PERIODIC, callback=atualizaDoDHT) # 180000: 3 minutos(em ms)


# Loop principal (infinito)
try:
    while True:
        if horaDoClimatempo: # Verifica o site do climatempo, se está na hora
            atualizaTempo(amb)
            horaDoClimatempo = False
        if horaDoDHT: # Verifica o sensor DHT, se está na hora
            atualizaDHT(amb)
            horaDoDHT = False
            
        verificaAmbiente() # Todos os sensores, incluindo fim de curso
        # analisa os fins de curso
        if fcFecha.value() == 1:
            estadoJanela = 'fechado'
            cmd = 'parar'
        elif fcAbre.value() == 1:
            estadoJanela = 'aberto'
            cmd = 'parar'        
        
        if cmd:    
            if estadoJanela not in ('aberto','abrindo') and cmd == 'abrir':
                abrirJanela()
                estadoJanela = 'abrindo'
                sleep(1)
                
            elif estadoJanela not in ('fechado','fechando') and cmd == 'fechar':
                fecharJanela()
                estadoJanela = 'fechando'
                sleep(1)
            
            else:
                paradaTotal()
                estadoJanela = 'parado'
                sleep(5)
            
            cmd = ''
           
except KeyboardInterrupt:
    pass

finally:    # Se o loop for interrompido, finaliza parando os timers
    print ("Acabou")
    tempSite.deinit()
    tempSensor.deinit()
    
