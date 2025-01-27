import socket
import threading
import json
import base64
import sqlite3
import os, sys
import datetime
from logzero import logger
import random
import string

from objects import echo, user
from modules import encoding
from modules import aes
from modules import config

from net.sendMessage import sendMessage
from net import changeChannel
from net import userMessage
from net import disconnect
from net import historyRequest
from net import leaveChannel

if not os.path.exists("data"):
	os.mkdir("data")

if not os.path.exists(r"data/key.txt"):
	key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
	with open(r"data/key.txt", "w") as f:
		f.write(key)
		logger.warning("No starterkey file detected")
		print("-----------------------------")
		logger.info("Welcome to Echo!")
		logger.info("Use the command /letmein [key] to be given the administrator role")
		logger.info("The key can be found in the data folder in your install directory")
		print("-----------------------------")

def ClientConnectionThread(conn, addr):
	try:
		logger.info("Client connected from " + str(addr))
		
		byteData = conn.recv(1024) # Receive serverInfoRequest
		data = encoding.DecodePlain(byteData) 
		
		sendMessage(conn, "", "serverInfo", server.RSAPublicToSend, enc=False)

		byteData = conn.recv(1024) # Receive clientSecret
		data = encoding.DecodePlain(byteData)

		userSecret = server.RSAPrivate.decrypt(base64.b64decode(data["data"]))

		sendMessage(conn, userSecret, "gotSecret", "")

		byteData = conn.recv(1024) # Receive connectionRequest
		data = encoding.DecodeEncrypted(byteData, userSecret)

		connectionRequest = json.loads(data["data"])

		currentUser = user.User(data["userid"], connectionRequest[0], userSecret, addr, conn)

		currentUser.connectionValid = True
		isServerFull = server.IsServerFull()
		if isServerFull:
			connInvalidReason = "Server is full"
			currentUser.connectionValid = False
			logger.warning("Client " + str(addr) + " tried to join but the server was full")
		validPassword = server.Authenticate(connectionRequest[1]);
		if validPassword == False:
			connInvalidReason = "Incorrect Password"
			currentUser.connectionValid = False
			logger.warning("Client " + str(addr) + " used incorrect password")
		isNotBanned = server.IsNotBanned(currentUser)
		if isNotBanned == False:
			connInvalidReason = "You are banned from this server"
			currentUser.connectionValid = False
			logger.warning("Client " + str(addr) + " tried to join but was banned")
		validID = server.ValidID(currentUser)
		if validID == False:
			connInvalidReason = "Invalid eID"
			currentUser.connectionValid = False
			logger.warning("Client " + str(addr) + " tried to join but was already connected from the same device")
		if connectionRequest[2] not in server.compatibleClientVers:
			connInvalidReason = "Incompatible Client version"
			currentUser.connectionValid = False
			logger.warning("Client " + str(addr) + " tried to join but was has an incompatible client version")
		validUsername = server.ValidUsername(currentUser)
		currentUser.username = validUsername
	
	except ConnectionResetError:
		logger.error("Client " + str(addr) + " disconnected during handshake")
		currentUser.connectionValid = False
	
	if currentUser.connectionValid == True:
		try:
			sendMessage(conn, userSecret, "CRAccepted", "")
			server.AddUser(currentUser)
			sendMessage(conn, userSecret, "serverData", server.packagedData)
			logger.info("Client " + str(addr) + " completed handshake")
			while currentUser.connectionValid:
				byteData = conn.recv(1024)
				data = encoding.DecodeEncrypted(byteData, currentUser.secret)
				logger.info("Received messagetype " + data["messagetype"] + " from client " + str(addr))
				if data["messagetype"] == "disconnect":
					disconnect.handle(conn, addr, currentUser, server, data) 
					break
				elif data["messagetype"] == "requestInfo":
					sendMessage(conn, userSecret, "serverData", server.packagedData)
				elif data["messagetype"] == "userMessage":
					userMessage.handle(conn, addr, currentUser, server, data) 
				elif data["messagetype"] == "changeChannel":
					changeChannel.handle(conn, addr, currentUser, server, data)
				elif data["messagetype"] == "historyRequest":
					historyRequest.handle(conn, addr, currentUser, server, data)
				elif data["messagetype"] == "leaveChannel":
					leaveChannel.handle(conn, addr, currentUser, server, data)
		except json.decoder.JSONDecodeError:
			logger.error("Received illegal disconnect from client " + str(addr))
			disconnect.handle(conn, addr, currentUser, server, data)
			currentUser.connectionValid = False
		except ConnectionResetError:
			logger.error("Received illegal disconnect from client " + str(addr))
			disconnect.handle(conn, addr, currentUser, server, data)
			currentUser.connectionValid = False
		except ConnectionAbortedError as e:
			if currentUser.connectionValid == False:
				pass
			else:
				logger.error(e)
	else:
		logger.warning("Client " + str(addr) + " failed handshake");
		sendMessage(conn, userSecret, "CRDenied", connInvalidReason)
		conn.close()

	conn.close()
	logger.info("Client " + str(addr) + " connection closed");

name = config.GetSetting("name", "Server")
channels = config.GetSetting("channels", "Server")
password = config.GetSetting("password", "Server")
port = config.GetSetting("port", "Server")
clientnums = config.GetSetting("clientnum", "Server")
motd = config.GetSetting("motd", "Server")
compatibleClientVers = config.GetSetting("compatibleClientVers", "Server")
strictBanning = config.GetSetting("strictBanning", "Server")
logger.info("Config loaded")

server = echo.Echo(name, "", port, password, channels, motd, clientnums, compatibleClientVers, strictBanning)
#server.initDB()
server.initAlchemy()
server.StartServer(ClientConnectionThread)

live_server = os.environ.get("ECHO_MYSQL_DB")
if not live_server:
	userInp = input("")
	if userInp == "q":
		server.StopServer()
		sys.exit()
else:
	while True:
		pass
