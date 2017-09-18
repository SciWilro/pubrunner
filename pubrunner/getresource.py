
import pubrunner
import sys
import argparse
import os
import git
import tempfile
import shutil
import logging
import traceback
import yaml
import json
import subprocess
import shlex
import wget
import gzip
import hashlib
import six
import six.moves.urllib as urllib
import time
from six.moves import reload_module
import ftplib
import ftputil
from collections import OrderedDict
import re

def calcSHA256(filename):
	return hashlib.sha256(open(filename, 'rb').read()).hexdigest()

def calcSHA256forDir(directory):
	sha256s = {}
	for filename in os.listdir(directory):
		sha256 = calcSHA256(os.path.join(directory,filename))
		sha256s[filename] = sha256
	return sha256s

def ftpDirListing(f):
	try:
		tmp = []
		f.retrlines('MLSD', tmp.append)
		listings = {}
		for t in tmp:
			split = t.split(';')
			name = split[-1].strip()
			attributes = [ tuple(a.split('=')) for a in split[0:-1] ]
			listing = { a:b for a,b in attributes }
			listings[name] = listing
	except ftplib.error_perm, resp:
		if str(resp) == "550 No files found":
			listings = []
		else:
			raise

	return listings

def ftpIsDir(url):
	url = url.replace("ftp://","")
	root = url.split('/')[0]
	parent = "/".join(url.split('/')[1:-1])
	basename = url.split('/')[-1]
	ftp = ftplib.FTP(root)
	ftp.login("anonymous", "ftplib")
	ftp.cwd(parent)
	listings = ftpDirListing(ftp)
	thingType = listings[basename]['type']
	assert thingType == 'file' or thingType == 'dir'
	return thingType == 'dir'

def download(url,out):
	if url.startswith('ftp'):
		#isDir = ftpIsDir(url)

		#hostname = url.replace("ftp://","").
		url = url.replace("ftp://","")
		hostname = url.split('/')[0]
		#parent = "/".join(url.split('/')[1:-1])
		path = "/".join(url.split('/')[1:])
		#basename = url.split('/')[-1]


		with ftputil.FTPHost(hostname, 'anonymous', 'secret') as host:
			isDir = host.path.isdir(path)
			isFile = host.path.isfile(path)
			assert isDir or isFile

			if isDir:
				assert os.path.isdir(out), "FTP path (%s) is a directory. Expect a directory as output" % url
				for filename in host.listdir(path):
					host.download(filename,os.path.join(out,filename))
			else:
				host.download(path,out)
		#if isDir:
		#	if not os.path.isdir(out):
		#		raise RuntimeError("FTP path (%s) is a directory. Expect a directory as output" % url)
			
			

		
		#ftpDirListing(url)

		#sys.exit(0)
	else:
		if os.path.isfile(out):
			os.unlink(out)

		wget.download(url,out,bar=None)

def gunzip(source,dest,deleteSource=False):
	with gzip.open(source, 'rb') as f_in, open(dest, 'wb') as f_out:
		shutil.copyfileobj(f_in, f_out)

	if deleteSource:
		os.unlink(source)

def getResourceLocation(resource):
	#homeDir = os.path.expanduser("~")
	homeDir = '/projects/bioracle/jake/pubrunnerTmp'
	baseDir = os.path.join(homeDir,'.pubrunner')
	thisResourceDir = os.path.join(baseDir,'resources',resource)
	return thisResourceDir

def getResourceInfo(resource):
	packagePath = os.path.dirname(pubrunner.__file__)
	resourceYamlPath = os.path.join(packagePath,'resources','%s.yml' % resource)
	with open(resourceYamlPath) as f:
		resourceInfo = yaml.load(f)

	return resourceInfo

def makeLocation(name,createDir=False):
	homeDir = '/projects/bioracle/jake/pubrunnerTmp'
	baseDir = os.path.join(homeDir,'.pubrunner')
	thisDir = os.path.join(baseDir,'workingDir',name)
	if createDir and not os.path.isdir(thisDir):
		os.makedirs(thisDir)
	return thisDir

def getResource(resource):
	print("Fetching resource: %s" % resource)

	#homeDir = os.path.expanduser("~")
	homeDir = '/projects/bioracle/jake/pubrunnerTmp'
	baseDir = os.path.join(homeDir,'.pubrunner')
	thisResourceDir = os.path.join(baseDir,'resources',resource)

	packagePath = os.path.dirname(pubrunner.__file__)
	resourceYamlPath = os.path.join(packagePath,'resources','%s.yml' % resource)
	assert os.path.isfile(resourceYamlPath), "Can not find appropriate file for resource: %s" % resource

	with open(resourceYamlPath) as f:
		resourceInfo = yaml.load(f)

	#print(json.dumps(resourceInfo,indent=2))

	if resourceInfo['type'] == 'git':
		assert isinstance(resourceInfo['url'], six.string_types), 'The URL for a git resource must be a single address'

		if os.path.isdir(thisResourceDir):
			# Assume it is an existing git repo
			repo = git.Repo(thisResourceDir)
			repo.remote().pull()
		else:
			os.makedirs(thisResourceDir)
			git.Repo.clone_from(resourceInfo["url"], thisResourceDir)
		return thisResourceDir
	elif resourceInfo['type'] == 'dir':
		assert isinstance(resourceInfo['url'], six.string_types) or isinstance(resourceInfo['url'],list), 'The URL for a dir resource must be a single or multiple addresses'
		if isinstance(resourceInfo['url'], six.string_types):
			urls = [resourceInfo['url']]
		else:
		 	urls = resourceInfo['url']

		if os.path.isdir(thisResourceDir):
			for url in urls:
				basename = url.split('/')[-1]
				assert isinstance(url,six.string_types), 'Each URL for the dir resource must be a string'
				download(url,os.path.join(thisResourceDir,basename))
		else:
		 	os.makedirs(thisResourceDir)
			for url in urls:
				basename = url.split('/')[-1]
				assert isinstance(url,six.string_types), 'Each URL for the dir resource must be a string'
				download(url,os.path.join(thisResourceDir,basename))
		
		if 'unzip' in resourceInfo and resourceInfo['unzip'] == True:
			for filename in os.listdir(thisResourceDir):
				if filename.endswith('.gz'):
					unzippedName = filename[:-3]
					gunzip(os.path.join(thisResourceDir,filename), os.path.join(thisResourceDir,unzippedName), deleteSource=True)

		return thisResourceDir
	else:
		raise RuntimeError("Unknown resource type (%s) for resource: %s" % (resourceInfo['type'],resource))
