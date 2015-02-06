import sys

#from lib import Project
#from lib import Options

import configparser
import logging
#import pymodbus
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pyspinel import Device
from quido import Device as kvido

appversion = "0.0.1"
appname = "polygon"
conffile = "../config/polygon.conf"
log_filename = "../log/polygon.log"


def parseConfFile():
	try:
		config = configparser.SafeConfigParser()
		config.read(conffile)
	except configparser.ParsingError, err:
		logger.exception('Could not parse:', err)
		#logger.error(msg, exc_info=True, *args)

	logger.info('Parsing config file')
	din = dict(config.items("QUIDO_IN"))
	dout = dict(config.items("QUIDO_OUT"))
#	print (din['address'])

	

if __name__ == '__main__':
	logging.basicConfig(filename=log_filename, level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
	logger = logging.getLogger(__name__)
	logger.info('Starting program')
	parseConfFile()
#	inClient = ModbusClient(din[address])
#	outClient = ModbusClient(dout[address])
#	rr = client.read_coils(1,1)
#	print rr
#	inClient.close()
#	outClient.close()
	a = kvido("192.168.16.232",10001)
	#n = a.query(0x30,"")
	#i = a.get_inputs_state()
	o = a.get_outputs_state()
	i = a.get_input_state(1)
	a.set_output_on(1)
	a.disconnect()
	print i
	sys.exit()