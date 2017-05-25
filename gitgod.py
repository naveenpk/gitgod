#!/usr/bin/env python3

import argparse

import datetime
import getopt
import glob
import os
import pickle
import platform
import re
import shutil
import subprocess
import sys
import time
import zlib


if sys.version_info < (3, 4):
	print('Python 3.4 or higher is required for gitgod')
	sys.exit(1)

from multiprocessing import Pool

os.environ['LC_ALL'] = 'C'

GNUPLOT_COMMON = 'set terminal png transparent size 640,240\nset size 1.0,1.0\n'
ON_LINUX = (platform.system() == 'Linux')
WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')

exectime_internal = 0.0
exectime_external = 0.0
time_start = time.time()

# By default, gnuplot is searched from path, but can be overridden with the
# environment variable "GNUPLOT"
gnuplot_cmd = 'gnuplot'
if 'GNUPLOT' in os.environ:
	gnuplot_cmd = os.environ['GNUPLOT']

conf = {
	'max_domains': 10,
	'max_ext_length': 10,
	'style': 'gitstats.css',
	'max_authors': 20,
	'authors_top': 5,
	'commit_begin': '',
	'commit_end': 'HEAD',
	'linear_linestats': 1,
	'project_name': '',
	'processes': 8,
	'start_date': ''
}

class GitGod(object):
	def __init__(self, src_dir, branches):
		self.total_commits_by_ordinal_day = {}
		self.total_commits_by_day_of_week = {}
		self.author_commits_by_ordinal_day = {}

		self.branches = branches
		self.src_dir = src_dir
		self.branch_commits = {}

	def get_branch_commits(self):

		for branch in self.branches:
			self.branch_commits[branch] = self.run_shell_cmds(['git rev-list --all --not $(git rev-list --all ^{0}) '
			                                                   '--pretty=format:"%at %ai %aN <%aE>"'.format(branch),
										                       'grep -v ^commit']).split('\n')

	def run_shell_cmds(self, cmds_list):
		cmd = cmds_list[0][0]
		do_pipe = cmds_list[0][1]
		proc = subprocess.Popen(cmd, stdout=subprocess.PIPE if do_pipe else subprocess.STDOUT,
		                        cwd=self.src_dir, shell=True)
		procs_list=[]
		for cmd_params in cmds_list[1:]:
			cmd = cmd_params[0]
			do_pipe = cmd_params[1]
			proc = subprocess.Popen(cmd, stdin=proc.stdout,
			                        stdout=subprocess.PIPE if do_pipe else subprocess.STDOUT, cwd=self.src_dir,
			                        shell=True)
			procs_list.append(proc)
		output = proc.communicate()[0]
		for proc in procs_list:
			proc.wait()
		return output.decode().rstrip('\n')

	def process_branch(self, branch_name):
		lines = self.run_shell_cmds([('git pull --quiet', True),
		                             ('git rev-list --no-merges --all --pretty=format:"%at %ai %aN <%aE>" HEAD', True),
		                             ('grep -v ^commit', True)]).split('\n')
		#print(lines)
		self.compute_branch_stats(lines)
		self.print_branch_stats()

	def compute_branch_stats(self, lines):
		#debugs(lines)
		for line in lines:
			parts = line.split(' ', 4)
			author = ''
			try:
				stamp = int(parts[0])
			except ValueError:
				stamp = 0
			timezone = parts[3]
			author, mail = parts[4].split('<', 1)
			author = author.rstrip()
			mail = mail.rstrip('>')
			domain = '?'
			if mail.find('@') != -1:
				domain = mail.rsplit('@', 1)[1]
			date = datetime.datetime.fromtimestamp(float(stamp))

			ordinal_date = date.toordinal()
			#debugs(ordinal_date)

			# day of week
			day = date.weekday()
			self.total_commits_by_day_of_week[day] = self.total_commits_by_day_of_week.get(day, 0) + 1

			# by ordinal day
			self.total_commits_by_ordinal_day[ordinal_date] = self.total_commits_by_ordinal_day.get(ordinal_date, 0) + 1

			if ordinal_date in self.author_commits_by_ordinal_day:
				self.author_commits_by_ordinal_day[ordinal_date][author] = \
			    self.author_commits_by_ordinal_day[ordinal_date].get(author, 0) + 1
			else:
				self.author_commits_by_ordinal_day[ordinal_date] = {}
				self.author_commits_by_ordinal_day[ordinal_date][author] = 1
			self.total_commits_by_ordinal_day[ordinal_date] = self.total_commits_by_ordinal_day.get(ordinal_date, 0) + 1

	def print_branch_stats(self):
		#print commits for last 7 days
		todays_ordinal_date = datetime.datetime.now().toordinal()
		for ord_day in range(todays_ordinal_date-10, todays_ordinal_date+1):
			if ord_day not in self.author_commits_by_ordinal_day:
				continue
			actual_date = datetime.datetime.fromordinal(ord_day)
			print('***** {0} ******'.format(actual_date.strftime('%Y-%m-%d')))
			for key,value in self.author_commits_by_ordinal_day[ord_day].items():
				print('{0}: {1}'.format(key, value))

	def debugs(self, debug_line, do_exit=True):
		print('######### OUTPUT ###########\n{0}'.format(debug_line))
		if do_exit:
			exit()

_settings = {}

def _process_args():
	parser = argparse.ArgumentParser()
	parser.add_argument('-s', '--source-dir', help='Source code dir')
	parser.add_argument('-b', '--branches', default=[], nargs='+', type=str, help='Comma separated list of branches')
	args = parser.parse_args()
	_settings['source_dir'] = args.source_dir
	_settings['branches'] = args.branches

	print('**** SETTINGS *****')
	print('Source Dir ==> {0}'.format(_settings['source_dir']))
	print('Branches ==> {0}'.format(_settings['branches']))

if __name__=='__main__':
	_process_args()
	git_god = GitGod(src_dir=_settings['source_dir'], branches=_settings['branches'])
	git_god.process_branch('master')

