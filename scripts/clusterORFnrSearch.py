#!/usr/bin/env python3

import sys
import os
from multiprocessing import Pool, Manager
import subprocess
from math import ceil

def makecall(call, stdout=None, stderr=None, stdin=None):
	'''
	Handles running subprocess.call. Used when making calls without multiprocessing
	'''
	if stdout == None and stderr == None and stdin == None:
		subprocess.call(call)
	elif stdout != None:
		with open(stdout, 'w') as outfl:
			if stderr != None:
				with open(stderr, 'w') as errfl:
					if stdin == None:
						subprocess.call(call, stdout=outfl, stderr=errfl)
					else:
						with open(stdin, 'r') as inFl:
							subprocess.call(call, stdin=inFl, stdout=outfl, stderr=errfl)
			elif stderr == None:
				if stdin == None:
					subprocess.call(call, stdout=outfl)
				else:
					with open(stdin, 'r') as inFl:
						subprocess.call(call, stdin=inFl, stdout=outfl)

	elif stderr != None and stdout == None:
		with open(stderr, 'w') as errfl:
			if stdin == None:
				subprocess.call(call, stderr=errfl)
			else:
				with open(stdin, 'r') as inFl:
					subprocess.call(call, stdin=inFl,  stderr=errfl)
		
	elif stdin != None and stderr == None and stdout == None:
		with open(stdin, 'r') as inFl:
			subprocess.call(call, stdin=inFl)


def getORFsFASTA(elementsFl, orffasta, outfasta):
	'''
	Write a new fasta with the orfs from orffasta for elements in elements.
	'''
	if type(elementsFl) == str:
		elements = set()
		with open(elementsFl, 'r') as inFl:
			for line in inFl:
				elements.add(line.strip())
	else:
		elements = elementsFl
	if os.path.isfile(outfasta):
		os.remove(outfasta)
	with open(orffasta, 'r') as inFl:
		for line in inFl:
			if line.startswith('>'):
				el = line.strip()[1:].split('.')[0]
				WRITE = False
				if el in elements:
					WRITE = True
			if WRITE:
				with open(outfasta, 'a') as outFl:
					outFl.write(line)

def blast2nrsummary(packet):
	'''
	Packet is just a list or tuple like:
	[blastOutputFile, nr]
	pid is % id threshold
	'''
	blast = packet[0]
	nr = packet[1]
	pid = packet[2]
	orfs = {}
	with open(blast, 'r') as blastFl:
		for line in blastFl:
			if line.startswith('#'):
				continue
			query, subject, pid, alnlen, mis, gapo, qstart, qend, sstart, send, evalue, bitscore = line.strip().split('\t')
			pid = float(pid)
			if pid >= min_pid:
				if query in orfs:
					orfs[query][subject] = {'blastresult':line.strip()}
				else:
					orfs[query] = {subject:{'blastresult':line.strip()}}
			
	with open(nr, 'r') as nrFl:
		for line in nrFl:
			if line.startswith('>'):
				acc = line.split(' ')[0][1:]
				for orf in orfs:
					if acc in orfs[orf]:
						orfs[orf][acc]['nrdesc'] = line.strip()
	outFlPth = '{0}.with_nr_descriptions.txt'.format(blast)
	fields = '# Fields: query id, subject id, % identity, alignment length, mismatches, gap opens, q. start, q. end, s. start, s. end, evalue, bit score\n'
	with open(outFlPth, 'w') as outFl:
		for orf in sorted(list(orfs.keys())):
			for hit in orfs[orf]:
				outFl.write(fields)
				outFl.write(orfs[orf][hit]['blastresult']+'\n')
				outFl.write(orfs[orf][hit]['nrdesc']+'\n\n')

def summarizeHits(hitsfl, outfl, maxhits=3):
	'''
	Parse and write summary for this routine.
	'''
	best_orfs = {}
	query = None
	with open(hitsfl, 'r') as infl:
		for line in sys.stdin:
			if line.startswith('LTR'):
				query, subject, pid, alnlen, mis, gapo, qstart, qend, sstart, send, evalue, bitscore = line.strip().split('\t')
				alnlen = int(alnlen)
				if query in best_orfs:
					best_orfs[query].append([alnlen])
				else:
					best_orfs[query] = [[alnlen]]
			elif line.startswith('>'):
				desc = ' '.join(line.strip().split(' ')[1:])
				best_orfs[query][-1].append(desc)

	with open(outfl, 'w') as outFl:
		for orf in best_orfs:
			best_orfs[orf].sort(reverse=True, key=lambda x:x[0])
			i = 0
			while i < maxhits and i < len(best_orfs[orf])-1:
				outFl.write('{0}\t{1}\t{2}\n'.format(orf, best_orfs[orf][i][0], best_orfs[orf][i][1]))
				i += 1

def help():
	print('''
	description:

		For use with PhILTH pipeline.
		Writes an individual FASTA file for ORFs for each cluster, and run blastp
		against nr. Hits satisfying the threshold are reported in an output file.


	usage:
		clusterORFnrSearch.py -cluster <path> -orffasta <path> -nr <path> -outdir <path> [-evalue <num>] [-min_pid <num>] [-p <int>] [-skipblast <path>]

		-cluster	A cluster file from WickerFam or MCL from the PhILTH pipeline.
		-nr		Path to nr blast-formatted database.
		-evalue		Evalue threshold for blastp
		-min_pid	Minimum percent id to include in output. default 60.0
		-outdir		Where to write the files.
		-p		processors. default 1
		-skipblast	path to file with list of three column rows: blast output, nr location, % identity threshold
		-maxhits	most hits to return in summary. Longest first.
	''', file=sys.stderr)


args = sys.argv

if '-cluster' not in args or '-orffasta' not in args or '-nr' not in args or len(args) < 7:
	help()
	sys.exit()


clusterFl = args[args.index('-cluster')+1]
outdir = args[args.index('-outdir')+1]
orffasta = args[args.index('-orffasta')+1]
nr = args[args.index('-nr')+1]

if '-p' in args:
	p = int(args[args.index('-p')+1])
else:
	p = 1
if '-min_pid' in args:
	min_pid = float(args[args.index('-min_pid')+1])
else:
	min_pid = 60.0
if '-evalue' in args:
	evalue = float(args[args.index('-evalue')+1])
else:
	evalue = 1e-2
if '-maxhits' in args:
	evalue = int(args[args.index('-maxhits')+1])
else:
	evalue = 3

fasta_basename = '.'.join(orffasta.split('/')[-1].split('.')[:-1])

if '-skipblast' not in args:
	blast_files = []
	with open(clusterFl, 'r') as inFl:
		i=0
		for line in inFl:
			outfasta = '{0}/{1}.cluster_{2}.orfs.prot.fasta'.format(outdir, fasta_basename, i)
			outbase = '{1}.cluster_{2}.orfs.prot.fasta'.format(outdir, fasta_basename, i)
			elements = set(line.strip().split())
			getORFsFASTA(elements, orffasta, outfasta)
			outblast = '{0}/{1}.blastp-nr.pid_{2}.evalue_{3}.tab'.format(outdir, outbase, min_pid, evalue)
			if os.path.isfile(outfasta):
				call = ['/home/derstudent/software/ncbi-blast-2.2.31+/bin/blastp', '-query', outfasta, '-db', nr, '-outfmt', '7', '-evalue', str(evalue), '-out', outblast, '-num_threads', str(p)]
				print(' '.join(call))
				makecall(call)
				if os.path.isfile(outblast):
					packet = (outblast, nr, min_pid)
					blast_files.append(packet)
			i+=1

	print('Done with getting cluster ORF FASTAs.', file=sys.stderr)

elif '-skipblast' in args:
	blast_files = []
	with open(args[args.index('-skipblast')+1], 'r') as blastoutputlist:
		for line in blastoutputlist:
			packet = line.strip().split('\t')
			blast_files.append(packet)

chunk_size = ceil(len(blast_files)/p)
with Pool(processes=p) as pl:
	pl.map(blast2nrsummary, blast_files, chunksize=chunk_size)
pl.join()

for fl in os.listdir(outdir):
	if fl.endswith('.with_nr_descriptions.txt'):
		newfl = '{0}.Summary'.format('.'.join(fl.split('.')[:-1]))
		summarizeHits(fl, newfl, maxhits)


print('All done.', file=sys.stderr)
