from twisted.words.protocols import irc
from twisted.internet import protocol
from twisted.internet import reactor

import ConfigParser
import json
import sys
import os
import sqlite3
import time

class twistedBot( irc.IRCClient ):

	def __init__( self ):
		lastMsg = ""
		self.loadBlacklist()

	def _get_nickname( self ):
		return self.factory.nickname

	nickname = property( _get_nickname )

	def signedOn( self ):
		self.join( self.factory.channel )
		print "Signed on as " + self.nickname

		self.conn = sqlite3.connect( self.factory.config.get( "General", "database_path" ) )
		self.cursor = self.conn.cursor()

	def joined(self, channel):
		print "Joined " + channel

	def action( self, user, channel, msg ):
		if not user:
			return

		msgFrom = user.split( '!', 1 )[0]

		self.logMessage( msgFrom, channel, msg, 'ACTION' )

	def privmsg( self, user, channel, msg ):
		if not user:
			return

		reply = ""

		msgFrom = user.split( '!', 1 )[0]

	 	if msgFrom in self.blacklist:
			return

		self.logMessage( msgFrom, channel, msg, 'PRIVMSG' )

		if msg.startswith( self.nickname ):
			reply = self.parseMsg( " ".join( msg.split( " " )[1:] ), channel, msgFrom )

		if reply != None and len( reply ) > 0:
			replyMsg = "%s: %s" % ( msgFrom, reply )
			self.msg( channel, replyMsg )
			self.logMessage( nickname, channel, replyMsg )

	def logMessage( self, user, channel, msg, type ):
		self.cursor.execute( u"INSERT INTO log VALUES (?,?,?,?,?)", ( channel.decode('utf-8'), user.decode('utf-8'), msg.decode('utf-8'), int( time.time() ), type.decode('utf-8') ) )
		self.conn.commit()

	def parseMsg( self, msg, channel, user ): 

		if msg.startswith( "source" ):
			return self.factory.config.get( "General", "source_url" )

		elif msg.startswith( "help" ):
			return "Logs the channel. View at http://lug.fltt.us"

		elif msg.startswith( "die" ):
 			if user == self.factory.owner:
				self.doQuit( user )
			else:
				self.msg( channel, "%s: Only owner can do that." % ( user, ) )

		elif msg.startswith( "part" ):
			if user == self.factory.owner:
				channels = msg.split( " " )[1:]
				for chan in channels:
					self.leave( chan )
			else:
				self.msg( channel, "%s: Only owner can do that." % ( user, ) )
	
		elif msg.startswith( "join" ):
			if user == self.factory.owner:
				channels = msg.split( " " )[1:]
				for chan in channels:
					self.join( chan )
			else:
				self.msg( channel, "%s: Only owner can do that." % ( user, ) )
		
		elif msg.startswith( "blacklist" ):
			if user == self.factory.owner:
				nicks = msg.split( " " )[1:]
				for nick in nicks:
					self.blacklist.append( nick )

				self.msg( channel, "Added %s to blacklist" % ( ", ".join( nicks ), ) )
			else:
				self.msg( channel, "%s: Only owner can do that." % ( user, ) )

		elif msg.startswith( "whitelist" ):
			if user == self.factory.owner:
				nicks = msg.split( " " )[1:]
				for nick in nicks:
					self.blacklist.remove( nick )

				self.msg( channel, "Removed %s from blacklist" % ( ", ".join( nicks ), ) )
			else:
				self.msg( channel, "%s: Only owner can do that." % ( user, ) )
		
		else:
			return ""

	def doQuit( self, user ):
		self.factory.isQuitting = True
		self.quit( "Disconnected by %s" % ( user, ) )
		self.saveBlacklist()

	def saveBlacklist( self ):
		blacklistFile = open( "blacklist.json", "w" )
		json.dump( self.blacklist, blacklistFile )
		blacklistFile.close()

	def loadBlacklist( self ):
		blacklistFile = open( "blacklist.json", "r" )
		self.blacklist = json.load( blacklistFile )
		blacklistFile.close()


class twistedBotFactory( protocol.ClientFactory ):
	protocol = twistedBot
	isQuitting = False

	def __init__( self, config ):
		self.channel = config.get( "IRC", "channel" )
		self.nickname = config.get( "IRC", "nickname" )

		self.source_url = config.get( "General", "source_url" )
		self.owner = config.get( "General", "owner" )

		self.config = config
	
	def clientConnectionLost( self, connector, reason ):
		if not self.isQuitting:
			print "Lost connection: " + str( reason ) 
			print "Reconnecting..."
			connector.connect()
		else:
			print "Client exiting..."
			reactor.stop()

	def clientConnectionFailed(self, connector, reason):
		print "Could not connect: " + str( reason )

if __name__ == "__main__":
	config = ConfigParser.ConfigParser()
	config.read( "bot.config" )

	server = config.get( "IRC", "server" )
	port = config.getint( "IRC", "port" )
		
	reactor.connectTCP( server, port, twistedBotFactory( config ) )
	reactor.run()
