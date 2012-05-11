from twisted.words.protocols import irc
from twisted.internet import protocol, reactor

from PIL import Image, ImageDraw, ImageFont

import brain

import ConfigParser
import twitter
import sys
import os
import random
import re
import textwrap
import pycurl
import json
import cStringIO


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

	def joined(self, channel):
		print "Joined " + channel

	def privmsg( self, user, channel, msg ):
		if not user:
			return

		msgFrom = user.split( '!', 1 )[0]

	 	if msgFrom.endswith( "bot" ) or msgFrom in self.blacklist:
			return

		isPrivateMsg = channel == self.nickname
		replyTo = channel
		replyMsg = ""
		reply = ""
		
		if isPrivateMsg:
			msg = " ".join( msg.split( " " )[1:] )
			replyTo = msgFrom
		else:
			replyMsg = "%s: " % ( msgFrom, )

		msg = msg.strip()

		if isPrivateMsg or msg.startswith( self.nickname ):
			reply = self.parseMsg( " ".join( msg.split( " " )[1:] ), channel, msgFrom )

		if reply == "" and ( msg.startswith( self.nickname ) or isPrivateMsg or random.random() <= self.factory.chattiness ): 
			reply = self.getsentence( msg )
			self.lastMsg = reply

		if reply != None and len( reply ) > 0:
			replyMsg += reply
			self.msg( replyTo, replyMsg )

	def parseMsg( self, msg, channel, user ): 

		if msg.startswith( "twitlast" ):
			if not hasattr(self, 'lastMsg') or self.lastMsg != "":
				return ""

			print self.lastMsg
			status = self.factory.api.PostUpdate( self.lastMsg )
			return self.factory.base + str( status.id )

		elif msg.startswith( "kittify" ):
			return self.kittify()

		elif msg.startswith( "kitlast" ):
			url = self.kittify()
			status = self.factory.api.PostUpdate( url )
			return self.factory.base + str( status.id ) + " " + url

		elif msg.startswith( "source" ):
			return self.factory.config.get( "General", "source_url" )

		elif msg.startswith( "help" ):
			return "Commands: twitlast - tweets the last message; source - link to bot's source; kittify - kittenify the last message; kitlast - kittenify and post image to twitter; help - this message"

		elif msg.startswith( "die" ):
 			if user == self.factory.owner:
				self.doQuit()
			else:
				self.me( channel, "fires first and watches %s writhing on the ground." % ( user, ) )

		elif msg.startswith( "join" ):
			if user == self.factory.owner:
				channels = msg.split( " " )[1:]
				for chan in channels:
					self.join( chan )
			else:
				self.me( channel, "kicks %s in the shin" % ( user, ) )
		
		elif msg.startswith( "blacklist" ):
			if user == self.factory.owner:
				nicks = msg.split( " " )[1:]
				for nick in nicks:
					self.blacklist.append( nick )

				self.msg( channel, "Added %s to blacklist" % ( ", ".join( nicks ), ) )
			else:
				self.me( channel, "kicks %s in the shin" % ( user, ) )

		elif msg.startswith( "whitelist" ):
			if user == self.factory.owner:
				nicks = msg.split( " " )[1:]
				for nick in nicks:
					self.blacklist.remove( nick )

				self.msg( channel, "Removed %s from blacklist" % ( ", ".join( nicks ), ) )
			else:
				self.me( channel, "kicks %s in the shin" % ( user, ) )
		
		else:
			return ""

	def doQuit( self ):
		self.factory.isQuitting = True
		self.quit( "Yes master" )
		self.saveBlacklist()

	def saveBlacklist( self ):
		blacklistFile = open( "blacklist.json", "w" )
		json.dump( self.blacklist, blacklistFile )
		blacklistFile.close()

	def loadBlacklist( self ):
		blacklistFile = open( "blacklist.json", "r" )
		self.blacklist = json.load( blacklistFile )
		blacklistFile.close()

	def kittify( self ):
		if self.lastMsg == "":
			return ""

		kitten = "kitten%d.jpg" % random.choice( range( 1, 10 ) )
		im = Image.open( "kittens/" + kitten )
		box = im.getbbox()
		width = box[2]
		height = box[3]
		fsize = 70
		font = ImageFont.truetype( "ArialBlack.ttf", fsize )

		while font.getsize( self.lastMsg )[0] > ( ( width * 2 ) - 100 ):
			fsize -= 2
			font = ImageFont.truetype( "ArialBlack.ttf", fsize )

		lines = textwrap.wrap( self.lastMsg, int( width / fsize * 1.65 ) )

		draw = ImageDraw.Draw( im )
		draw.text( ( 10, 10 ), lines[0], font=font, fill="white" )

		if len( lines ) > 1:
			draw.text( ( 10, height - 10 - fsize ), lines[-1], font=font )

		im.save( "tmp.jpg" )

		response = cStringIO.StringIO()

		c = pycurl.Curl()

		values = [
			( "key", self.factory.imgur_token ),
			( "image", ( c.FORM_FILE, "tmp.jpg" ) )
		]
		
		c.setopt( c.URL, "http://api.imgur.com/2/upload.json" )
		c.setopt( c.HTTPPOST, values )
		c.setopt( c.WRITEFUNCTION, response.write )
		c.perform()
		c.close()
		ret = json.loads( response.getvalue() )
		return str( ret[ 'upload' ][ 'links' ][ 'original' ] )

		
	def getsentence(self, msg):
		brain.add_to_brain(msg, self.factory.chain_length, write_to_file=True)
		sentence = brain.generate_sentence(msg, self.factory.chain_length, self.factory.max_words)
		if sentence:
			return sentence
		else:
			return msg


class twistedBotFactory( protocol.ClientFactory ):
	protocol = twistedBot
	isQuitting = False

	def __init__( self, config ):
		self.channel = config.get( "IRC", "channel" )
		self.nickname = config.get( "IRC", "nickname" )

		self.chain_length = config.getint( "Markov", "chain_length" )
		self.chattiness = config.getfloat( "Markov", "chattiness" )
		self.max_words = config.getint( "Markov", "max_words" )

		self.source_url = config.get( "General", "source_url" )
		self.owner = config.get( "General", "owner" )

		self.base = config.get( "Twitter", "base_url" )
		self.api = twitter.Api( 
								config.get( "Twitter", "consumer_key" ), 
								config.get( "Twitter", "consumer_secret" ), 
								config.get( "Twitter", "access_token_key" ), 
								config.get( "Twitter", "access_token_secret" )
							  )

		self.imgur_token = config.get( "Kittify", "imgur_token" );

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
	chain_length = config.getint( "Markov", "chain_length" )
		
	if os.path.exists( 'training_text.txt' ):
		f = open( 'training_text.txt', 'r' )

		for line in f:
			brain.add_to_brain( line.upper(), chain_length )

		print "brain loaded"
		f.close()

	reactor.connectTCP( server, port, twistedBotFactory( config ) )
	reactor.run()
