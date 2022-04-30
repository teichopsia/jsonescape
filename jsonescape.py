#!/usr/bin/env python3

'''
this script is a proof of concept for a stream filter to convert broken json into something usable to scrub downstream

the use case here is an ingest stream of squid httpd-like access logs being processed into json but the incoming log
stream did nothing to prevent json/like urls from passing through unescaped

so samples ingested have raw json in the url and other mangling.

the goal here was to fix ingest of select records without reindexing everything from the given edge device (patch)
'''

import pprint
import sys
import json
import traceback
import urllib
import base64

def eprint(*a,**b):
	if False:
		print(*a,**b)

class emitter(object):
	def __predicate(self,t,pred='pred'):
		return '__lex_rule_{}'.format(t[pred])
	def __init__(self,src,dispatch):
		self.src=src
		self.dispatch=dispatch
		self.lastlex=''
		for token in dispatch:
			k=[self,self.__predicate(dispatch[token])]
			if not hasattr(*k):
				s=k+[False]
				setattr(*s)
	def doset(self,a):
		setattr(self,a,True)
	def doreset(self,a):
		setattr(self,a,False)
	def doinvert(self,a):
		setattr(self,a,not getattr(self,a))
	def donop(self,a):
		pass
	def ridentity(self,a):
		return a
	def rescape(self,a):
		return '%%%X'%(ord(a))
	def __emit(self,token):
		h={True:'if',False:'else'}
		r=''
		if self.lastlex == '\\':
			if token!='"':
				r=self.rescape(token)
			else:
				r='\\\\"'
		else:
			eprint(token,
				'q:',getattr(self,'__lex_rule_quoted'),
				'n:',getattr(self,'__lex_rule_nested'),
				file=sys.stderr,end=' ')
			if token in self.dispatch:
				ruleset=self.dispatch[token]
				#import pdb;pdb.set_trace()
				z=h[getattr(self,self.__predicate(ruleset))]
				op,ret=ruleset[z]['op'],ruleset[z]['ret']
				ff=self.__predicate(ruleset[z],'at')
				getattr(self,op)(ff)
				r=getattr(self,ret)(token)
				eprint('?:',ruleset['pred'],'op: {}({})'.format(op,ff.split('_')[-1]),'ret:',ret,'=>',r,file=sys.stderr,end='')
			elif r == '\\':
				pass #r=''
			else:
				r=token
			eprint('',file=sys.stderr)
		self.lastlex=token
		return r
	def __call__(self):
		def __callhelper(z):
			for c in z:
				yield self.__emit(c)
		return ''.join([k for k in __callhelper(self.src)])

class ast(object):
	def __init__(self):
		self.top={}
	def _on(self,t):
		self.top.update({t:{}})
		self.curr=self.top[t]
		return self
	def _if(self,p):
		self.curr['pred']=p
		self.curr['if']={}
		self.curr['else']={}
		self.curri=self.curr['if']
		self.curre=self.curr['else']
		return self
	def _then(self,f,p):
		self.curri.update({'op':f,'at':p})
		self.currr=self.curri
		return self
	def _else(self,f,p):
		self.curre.update({'op':f,'at':p})
		self.currr=self.curre
		return self
	def _return(self,r):
		self.currr.update({'ret':r})
		return self
	def __call__(self):
		return self.top

if __name__ == '__main__':
	''' this is two escape rule sets using one another as predicates
	pass any token through unless it's a quote or brackets
	for quotes we only pass them through if we're not in a pair currently (unnested)
	for brackets they're escaped unless we're outside quotes

	if ":
		if NESTED:
			escape(token)
		else:
			toggle(QUOTED)
			return(token)
	if {:
		if QUOTED:
			set(NESTED)
			escape(token)
		else:
			return(token)
	if }:
		if QUOTED:
			clear(NESTED)
			escape(token)
		else:
			return(token)
	default:
		return(token)
	'''
	engine=(ast()
	._on('"')
		._if('nested')
		._then('donop','quoted')._return('rescape')
		._else('doinvert','quoted')._return('ridentity')
	._on('{')
		._if('quoted')
		._then('doset','nested')._return('rescape')
		._else('donop','nested')._return('ridentity')
	._on('}')
		._if('quoted')
		._then('doreset','nested')._return('rescape')
		._else('donop','nested')._return('ridentity')
	)
	'''
	all above produces this but is slightly easier to read:

	'"':{'pred':'nested',											#if token is "
		'if':{'at':'quoted','op':'donop','ret':'rescape'},			#if 'nested' true, dont modify quote and escape token
		'else':{'at':'quoted','op':'doinvert','ret':'ridentity'}},	#else toggle quoted and return token as is
	'{':{'pred':'quoted',											#if token is {
		'if':{'at':'nested','op':'doset','ret':'rescape'},			#if 'quoted' true, enable nested and escape token
		'else':{'at':'nested','op':'donop','ret':'ridentity'}},		#else leave 'nested' as is and return token as is
	'}':{'pred':'quoted',											#if token is }
		'if':{'at':'nested','op':'doreset','ret':'rescape'},		#if 'quoted' true, disable nested and escape token
		'else':{'at':'nested','op':'donop','ret':'ridentity'}},		#else leave 'nested' as is and return token as is
	'''
		
	with open(sys.argv[1],'rt') if len(sys.argv)>1 else sys.stdin as ingest:
		for lineno,line in enumerate(ingest):
			if not line.find('{'):
				k=emitter(line,engine())
				tryline=k()
				try:
					a={}
					a=json.loads(tryline)
				except ValueError:
					et,ev,etb=sys.exc_info()
					print(lineno,'failed:',end='',file=sys.stderr)
					print(base64.b64encode(str.encode(line)),end='',file=sys.stderr)
					print(base64.b64encode(str.encode(tryline)),end='',file=sys.stderr)
					print('tb=',base64.b64encode(str.encode(''.join(traceback.format_tb(etb)))),file=sys.stderr)
					sys.stderr.flush()
				else:
					if True:
						print(json.dumps(a))
					else:
						pprint.pprint(a)
					eprint(lineno,'ok',file=sys.stderr)
