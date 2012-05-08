from twisted.words.protocols import irc
from twisted.internet import protocol

import brain

import ConfigParser
import twitter
import sys
import os
import random
import re
import Image, ImageDraw, ImageFont
import textwrap
import pycurl
import json
import cStringIO
from twisted.internet import reactor

class twistedBot( irc.IRCClient ):
	def __init__( self ):
		lastMsg = ""

	def _get_nickname( self ):
		return self.factory.nickname

	nickname = property( _get_nickname )

	def signedOn( self ):
		self.join( self.factory.channel )
		print "Signed on as " + self.nickname

	def joined(self, channel):
		print "Joined " + channel

	def privmsg( self, user, channel, msg ):
		if not user or user.endswith( "bot" ):
			return
		
		isPrivateMsg = channel == self.nickname
		msgFrom = user.split( '!', 1 )[0]
		replyTo = channel
		replyMsg = ""
		
		if isPrivateMsg:
			msg = msg.split( " " )[1:].join( " " )
			replyTo = msgFrom
		else:
			replyMsg = "%s: " % ( msgFrom, )

		msg = msg.strip()
		reply = self.parseMsg( msg )

		if reply == "" and ( msg.startswith( self.nickname ) or isPrivateMsg or random.random() <= self.factory.chattiness ): 
			reply = self.getsentence( msg )

		if reply != "":
			replyMsg += reply
			self.lastMsg = reply
			self.msg( replyTo, replyMsg )

	def parseMsg( self, msg ): 

		if msg.startswith( "twitlast" ):
			if not hasattr(self, 'lastMsg') or self.lastMsg != "":
				return ""

			print self.lastMsg
			status = self.factory.api.PostUpdate( self.lastMsg )
			return base + str( status.id )

		elif msg.startswith( "kittify" ):
			return self.kittify()

		elif msg.startswith( "kitlast" ):
			url = self.kittify()
			status = self.factory.api.PostUpdate( url )
			return self.base + str( status.id ) + " " + url

		elif msg.startswith( "source" ):
			return self.config.get( "General", "source_url" )

		elif msg.startswith( "help" ):
			return "Commands: twitlast - tweets the last message; source - link to bot's source; kittify - kittenify the last message; kitlast - kittenify and post image to twitter; help - this message"

		else:
			return ""

	def kittify( self ):
		if not hasattr( self, 'lastMsg' ) or self.lastMsg == "":
			return ""

		print self.lastMsg

		kitten = "kitten%d.jpg" % random.choice( range( 1, 10 ) )
		im = Image.open( "kittens/" + kitten )
		box = im.getbbox()
		width = box[2]
		height = box[3]
		fsize = 70
		lines = textwrap.wrap( self.lastMsg, int( width / fsize * 1.65 ) )

		while len(lines) > 2:
			fsize -= 2
			lines = textwrap.wrap( self.lastMsg, int( width / fsize * 1.65 ) )

		draw = ImageDraw.Draw( im )
		font = ImageFont.truetype( "Arial.ttf", fsize )
		draw.text( ( 10, 10 ), lines[0], font=font, fill="white" )

		if len( lines ) > 1:
			draw.text( ( 10, height - 10 - fsize ), lines[-1], font=font )

		im.save( "tmp.jpg" )

		response = cStringIO.StringIO()

		c = pycurl.Curl()

		values = [
			( "key", self.imgur_token ),
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

	def __init__( self, config ):
		self.channel = config.get( "IRC", "channel" )
		self.nickname = config.get( "IRC", "nickname" )

		self.chain_length = config.getint( "Markov", "chain_length" )
		self.chattiness = config.getfloat( "Markov", "chattiness" )
		self.max_words = config.getint( "Markov", "max_words" )

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
		print "Lost connection " + str( reason ) + ", reconnection"
		connector.connect()

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
