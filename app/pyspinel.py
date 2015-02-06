## This file is part of pyspinel.

## pyspinel is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 2 of the License, or
## (at your option) any later version.

## pyspinel is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with pyspinel.  If not, see <http://www.gnu.org/licenses/>.

"""Spinel 97 binary protocol implementation"""

import socket #for socket communication
import struct #for binary data packing
from random import randint #for sig generation

check_checksums = True #calculate checksums for received packets
check_packet_structure = True #check received packets for the right mask
log = True

################################################################
####                   PROTOCOL SPECIFICATION               ####
################################################################

PRE = 0x2a #the '*' is the packet prefix character
FRM = 0x61 #the 'a' is the packet format specification character, because ord('a') == 97
CR  = 0x0d # carriage return character
broadcast_address = 0xff #all devices react, no reply sent
universal_address = 0xfe #device reacts as a whole, reply contains its real ddress
ACK = {
	0x00 : "OK",
	0x01 : "Unknown error",
	0x02 : "Invalid instruction",
	0x03 : "Invalid instruction parameters",
	0x04 : "Permission denied", #write error, too low data, channel disabled, other requirements not met
	0x05 : "Device malfunction",
	0x06 : "Data not available",
	0x0d : "Digital input state change", #automatically sent message
	0x0e : "Continuous measurement", #automatically sent, repeatedly sending measured data
	0x0f : "Range overrun" #automatically sent
	}

if log:
	log_file = open('spinel97.log', 'a')
	

################################################################
####                   COMMUNICATION CLASSES                ####
################################################################

class Device(object):
	"""Class representing a device that communicates through the Spinel 97 protocol"""
	def __init__(self, ip, port=10001):
		"""Device(ip[, port])

		Initialize the device communication relay.

		Parameters
		----------
		ip : str
			IPv4 address of the device
		port : int
			number of the port used for communication
			defaults to 10001 (UDP)
		"""
		#self.socket = create_connection((ip,port)) #connect the socket to the device and store the returned default socket object
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.socket.connect((ip, port))

	def disconnect(self):
		"""Class representing a device that communicates through the Spinel 97 protocol"""
		self.socket.shutdown(1)
		self.socket.close()

	def query(self, instruction, parameters='', address=universal_address, receive=True):
		"""query(instruction[, parameters[, address[, receive]]])

		Query the module for a response with the given instruction, possibly with additional instruction parameters.
		Unless the address is specified, the universal address is used.
		A response from the device will be received at the end. This can be overriden by the receive parameter which is useful for debugging purposes when using the universal address as the response would contain the real address. The response must be then retreived by a separate :func:`receive` call, otherwise further communication will be blocked.

		Parameters
		----------
		instruction : int
			a Spinel 97 protocol instruction,
			specified as int (use the 0xab int notation for easier input)
		parameters : str
			parameters to the instruction as a string representing bytes in hex
			this apporach is more flexible as different implementaions pack the parameters array differently
			defaults to empty string '' (as not all instructions have parameters)
		address : int 
			address of the module, can be e.g. a channel number
			or a special address:
				0xff (255) - broadcast address, all devices react
					there is no real response from the device
				0xfe (254) - universal address, the device reacts as a whole
					response would contain the actual address
			the universal address is used by default
		receive : bool
			if True (default) the device response is received by :func:`receive`
			otherwise the response must be received by a separate :func:`receive` call

		Returns
		-------
		data : str or None
			string of chars, each representing 1B
			this is because other methods may want to unpack data differently
			returns None if broadcast address was used (as devices don't respond to this address) or if receive parameter was set to False
			
		Raises
		------
		the same Errors as :func:`receive` and also ValueError on unexpected ADR, provided the response will be received
		"""
		num = 5 + len(parameters) #ADR+SIG+INST+SUM+CR+ DATA
		self.current_sig = randint(0, 255) #packet signature
		SUM = 255 - (139 + num + address +self.current_sig + instruction) #97 + 42 (*) = 139
		for param in parameters:
			SUM -= ord(param)
		SUM = abs(SUM % 256)
		#while SUM < 0: #simulate byte overrun
		#	SUM += 256 #must be 1B size
		packet = struct.pack('>2Bh3B', PRE, FRM, num, address, self.current_sig, instruction) + parameters
		packet += struct.pack('2B', SUM, CR)
		self.socket.send(packet)
		if log:
			log_file.write(packet + "\n")
		if address == broadcast_address or not receive: #broadcast address, no response should be received OR we don't want to receive anything
			return None
		else: #should get a response
			adr, data = self.receive()
			if adr != address and address != universal_address:
				raise ValueError("Wrong packet address ADR, expected " + str(address) + " , got " + str(adr))
			else:
				return data

	def receive(self):
		"""receive()

		Receive a response from the device.

		Returns
		-------
		address : int
			address of the module from which the response came
		data : str
			string of chars, each representing 1B
			this is because other methods may want to unpack data differently

		Raises
		------
		ValueError
			if check_packet_structure is True, raises on wrong PRE or FRM 
			if check_checksums is True, raises on wrong SUM
			raises in unexptected SIG 
		RuntimeError
			packet always checked if ACK is other than 0x00 (OK)
			otherwise raises with ACK error message from ACK dictionary
		"""
		packet = self.socket.recv(7) #get the packet header
		if log:
			log_file.write(packet)
		pre, frm, num, address, sig, ack = struct.unpack('>2BH3B', packet)
		packet = self.socket.recv(num)
		if log:
			log_file.write(packet + "\n")
		data = packet[:-2] #without SUM and CR 
		if check_packet_structure:
			cr = packet[-1]
			if pre != PRE:
				raise ValueError("Wrong packet prefix PRE, expected " + str(PRE) + " got " + str(pre))
			if frm != FRM:
				raise ValueError("Wrong packet format FRM, expected " + str(FRM) + " got " + str(frm))
			if cr != chr(CR):
				raise ValueError("Wrong packet ending character CR, expected " + str(CR) + " , got " + cr)
		if sig != self.current_sig:
			raise ValueError("Wrong packet signature SIG, expected " + str(self.current_sig) + " , got " + str(sig))
		if ack != 0:
			raise RuntimeError("Error reported by ACK: " + ACK[ack])
		if check_checksums:
			SUM = packet[-2]
			SUM2 = 255 - (139 + num + address + sig + ack)
			for dat in data:
				SUM2 -= ord(dat)
			SUM2 = abs(SUM2 % 256)
			SUM2 = chr(SUM2)
			if SUM2 != SUM:
				raise ValueError("Wrong packet checksum SUM, expected " + SUM2 + " , got " + SUM)
		return address, data

	def instruct(self, instruction, parameters='', address=universal_address):
		"""instruct(instruction, [parameters[, address]])
		
		Instruct the module specified by its address with the given instruction, possibly with additional instruction parameters.
		A response is always received and processed.

		The parameters are the same as for :func:`query`.

		Returns True if everything was ok, False otherwise.
		"""
		try:
			self.query(instruction, parameters, address, True)
			return True
		except(ValueError, RuntimeError):
			return False