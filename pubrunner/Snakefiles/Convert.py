import sys
import os
import re
import json
from collections import Counter,defaultdict
import pubrunner
import random
import shutil

# https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks
def chunks(l, n):
	"""Yield successive n-sized chunks from l."""
	for i in range(0, len(l), n):
		yield l[i:i + n]

def findFiles(dirName):
	allFiles = []
	for root, dirs, files in os.walk(dirName):
		allFiles += [ os.path.join(root,f) for f in files ]
	
	# We're going to extract the last set of digits from each filename and sort by that
	nums = [ re.findall('[0-9]+',f) for f in allFiles ]
	nums = [ 0 if num == [] else int(num[-1]) for num in nums ]
	sortedByNum = sorted(list(zip(nums,allFiles)))
	sortedFilepaths = [ filepath for num,filepath in sortedByNum ]
	
	return sortedFilepaths

class OutputFileNamer:
	def __init__(self,directory,fileFormat):
		self.directory = directory
		self.fileFormat = fileFormat
		self.i = 0

	def next(self):
		for _ in range(10000):
			outputFile = os.path.join(self.directory,self.fileFormat % self.i)
			self.i += 1
			if not os.path.isfile(outputFile):
				return outputFile
		raise RuntimeError("Unable to create an output file that doesn't already exist")

snakemakeExec = shutil.which('snakemake')

requiredEnvironmentalVariables = ["INDIR","INFORMAT","OUTDIR","OUTFORMAT","CHUNKSIZE"]
missingVariables = []
for v in requiredEnvironmentalVariables:
	if os.environ.get(v) is None:
		missingVariables.append(v)

if not missingVariables == []:
	print("ERROR: Missing required environmental variables: %s" % (str(missingVariables)))
	print("This Snakefile uses environmental variables as input parameters")
	print()
	print("Example usage:")
	print("  INDIR=PMCOA INFORMAT=pmcxml OUTDIR=PMCOA-converted OUTFORMAT=txt CHUNKSIZE=10000 snakemake -s %s" % __file__)
	print()
	print("  INDIR is the input directory of the resource (e.g. Pubmed, PMC, etc)")
	print("  INFORMAT is the input format (e.g. pubmedxml, pmcxml, marcxml, etc)")
	print("  OUTDIR is the output directory for the converted files")
	print("  OUTFORMAT is the output format for the converted data (e.g. bioc, txt)")
	print("  CHUNKSIZE is the number of files to group into an output file")
	sys.exit(1)

#inDir = 'PMCOA_TWOJOURNALS'
inDir = os.environ.get("INDIR")
inFormat = os.environ.get("INFORMAT")
#outDir = 'PMCOA_TWOJOURNAL.converted'
outDir = os.environ.get("OUTDIR")
outFormat = os.environ.get("OUTFORMAT")
maxChunkSize = int(os.environ.get("CHUNKSIZE"))
#outPattern = 'converted.%04d.txt'
#outPattern = os.environ.get("OUTPATTERN")
outPattern = os.path.basename(inDir) + ".converted.%08d." + outFormat
#chunkFile = 'PMCOA_TWOJOURNALS.converted.chunks.json'
chunkFile = outDir + '.json'


files = findFiles(inDir)

if not os.path.isdir(outDir):
	os.makedirs(outDir)

assignedChunks = {}
if os.path.isfile(chunkFile):
	with open(chunkFile) as inF:
		prevOutputFilesWithChunks = json.load(inF)
	for outputFile,chunk in prevOutputFilesWithChunks.items():
		assert isinstance(chunk,list)
		for f in chunk:
			assert not f in assignedChunks
			assignedChunks[f] = outputFile

if sys.argv[0] == snakemakeExec:
	# We'll check if any previous input files have disappearted, and set that chunk to dirty (so it is reprocessed)
	filesSet = set(files)
	missingFiles = [ f for f in assignedChunks.keys() if not f in filesSet ]
	dirtyOutputFiles = set( [ assignedChunks[f] for f in missingFiles ] )
	for f in missingFiles:
		del assignedChunks[f]

	randNum = random.randint(0,10000)
	with open('rand%08d.txt' % randNum,'w') as f:
		f.write(str(sys.argv) + "\n")


	# Next we'll find out how many files are assigned to each chunk
	#assignedChunkSizes = Counter()
	#for outputFile in assignedChunks.values():
	#	assignedChunkSizes[outputFile] += 1

	if len(assignedChunks) > 0:
		# We're just take the last chunk alphabetically
		currentChunk = sorted(assignedChunks.values())[-1]
		currentChunkSize = len( [ f for f in assignedChunks.values() if f == currentChunk ] )
	else:
		currentChunk = None
		currentChunkSize = 0

	outputFileNamer = OutputFileNamer(outDir,outPattern)

	for f in files:
		if not f in assignedChunks:
			if currentChunk is None or currentChunkSize >= maxChunkSize:
				currentChunk = outputFileNamer.next()
				print("NEW",currentChunk)
				currentChunkSize = 0
			
			assignedChunks[f] = currentChunk
			dirtyOutputFiles.add(currentChunk)
			currentChunkSize += 1

	#print(assignedChunks)
	#sys.exit(0)

	print(dirtyOutputFiles)
	# Remove any dirty files to force them to be recalculated
	for dirtyOutputFile in dirtyOutputFiles:
		print(dirtyOutputFile)
		if os.path.isfile(dirtyOutputFile):
			os.unlink(dirtyOutputFile)
			print("Removing:", dirtyOutputFile)

	outputFilesWithChunks = defaultdict(list)
	for f,outputFile in assignedChunks.items():
		outputFilesWithChunks[outputFile].append(f)

	with open(chunkFile,'w') as outF:
		json.dump(outputFilesWithChunks,outF,indent=2,sort_keys=True)
else:
	outputFilesWithChunks = prevOutputFilesWithChunks

expectedFiles = sorted(outputFilesWithChunks.keys())

localrules: all

rule all:
	input: expectedFiles

for outputFile,chunk in outputFilesWithChunks.items():
	#commaDelimitedInputFiles = ",".join(chunk).replace('(','\\(').replace(')','\\)')
	rule:
		input: chunk
		output: outputFile
		#shell: "pubrunner_convert --i $(echo '{input}' | tr ' ' ',') --iFormat %s --o {output} --oFormat %s" % (inFormat,outFormat)
		run:
			inputFileList = list(input)
			outputFile = output[0]
			pubrunner.convertFiles(inputFileList,inFormat,outputFile,outFormat)
		
	
	#commaDelimitedInputFiles = ",".join(chunk).replace('(','\\(').replace(')','\\)')
		#shell:
		#	"""
		#		echo '{commaDelimitedInputFiles}' | wc > {output}
		#	"""
		#shell: "pubrunner_convert --i %s --iFormat %s --o {output} --oFormat %s" % (commaDelimitedInputFiles,inFormat,outFormat)
		#shell: "echo '%s' > {output}" % ",".join(chunk).replace('(','\\(').replace(')','\\)')
			#shell: "echo {input} > converted.txt"
