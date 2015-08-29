#!/usr/bin/python

import urllib2
import urllib #there's a reason for this
import csvkit 
import xlrd
from bs4 import BeautifulSoup
import networkx
import re
import os
import json
import time
import StringIO

root_page = 'http://ec.europa.eu/commission/'
weighting_source = '''https://docs.google.com/spreadsheets/d/1nCDV4LTyKUfoviiUz4U1sOlDulO6wH40G9fR9J2NinA/pub?gid=1008557036&single=true&output=csv''' #contains output from a survey of who is important
#lobbysource = '''http://ec.europa.eu/transparencyregister/public/consultation/statistics.do?action=getLobbyistsExcel&fileType=XLS_NEW''' #a register of lobbies is here
lobbysource = './full_export_new.xls'
staff = []

def get_weighting_data(source):
	survey = urllib2.urlopen(source)
	reader = csvkit.py2.CSVKitDictReader(survey)
	for row in reader:
		if row[u'Timestamp'] == u'% of a Juncker unit':
			return row #get survey material as a lookup table

def soupify(uri):
	#helper to avoid repeating getting the page and loading it into parser
	page = urllib2.urlopen(uri).read()
	soup = BeautifulSoup(page, 'lxml')
	return soup

def get_graphs():
	graphs = {}
	fs = (os.walk('Graphs').next())[2]
	for f in fs:
		if '.json' in f:
			with open(f) as fo:
				try:
					g = networkx.readwrite.json_graph.adjacency_graph(json.read(fo), multigraph=True)
					graphs[(f)] = g
				except IOError:
					print 'not a Lobster graph: ', f
				fo.close()
	return graphs

def save_graphs(graphs):
	for g,d in graphs.items():
		with g as f:
			open(f, 'w')
			data = networkx.readwrite.json_graph.adjacency_data(d)
			s = json.dump(f, data)
			f.close()
				
				

def get_lobbyists_clients(source_uri):

	#data = urllib.urlretrieve(source_uri)
	#xlrd doesn't like strings, only file names. so it's either use urllib2 and StringIO or urllib.urlretrieve. in fact StringIO won't save you because open_workbook() accepts only a path, not a file-like
	#also the xls is 25MB and about 3 in 5 attempts cock out, so we'll use a local copy
	book = xlrd.open_workbook(source_uri)
	sn = (book.sheet_names())[0]
	#get the sheet name
	sheet = book.sheet_by_name(sn)
	#open the sheet. cor, xlrd is picky.
	column_names = sheet.row_values(0)
	#this is how you get the headers. as I say, picky
	client_lobbyist_mapping = {}
	for row_number in range(sheet.nrows): #nrows returns count of rows
		r = sheet.row_values(row_number) #address each row by its index number
		row = dict(zip(column_names,r)) #make a dict with the column names
		if row['Clients']:
			if u'No clients' not in row['Clients']:
				for client in (row['Clients']).split(','):
					if client != 'S.A.': #French and Spanish people put commas in front of this
						client_lobbyist_mapping[(client)] = row['(Organisation) name'] 
		else:
			if row['Person with legal responsibility']:
				client_lobbyist_mapping[(row['(Organisation) name'])] = row['Person with legal responsibility']
	#data.close()
	return client_lobbyist_mapping

	#we should now have a mapping of clients to lobbyists in a Python dict.

def get_weighting(dept, job, weightings):
	if job == u'President':
		return 1	
	if job == u'First Vice-President':
		return 0.85*0.7 #vp rank * average of the project teams' ranking. I fucking forgot the guy
	if dept == u'Budget & Human Resources':
		return 0.85*.07
	job_weight = weightings[(job)]
	dept_weight = weightings[(dept)]
	return float(dept_weight) * float(job_weight) #returns weighting from the survey data. finds job title and department. department weighting multiplied by job weighting, which is normalised to the average.

def add_to_graph(meeting, graphs, graph_id, lobbyists):
#this is a bit complicated. unlike the Lobster PoC, we have staffers and lobbyists as intermediaries between the Powerful Ones. therefore it's not just a list of (lobby,minister) tuples. as a result, we have to use the add_path method.       	
	def add_path_wrapper(path, meeting, graphs, graph_id):
		if graph_id in graphs:
			graph = graphs[(graph_id)]
		else:
			graph = networkx.MultiGraph(weighted=True)
			graphs[(graph_id)] = graph
		graph.add_path(path, date=meeting['date'], locale=meeting['locale'], subject=meeting['subject'], weight=meeting['weight'])	#wrapper to avoid repeating myself		
	paths = []
	lobbies = [meeting['commissioner']] #the path begins with the commissioner
	for lobby in meeting['lobby']: # one path per commissioner-lobby pairing
		if lobby in lobbyists: # if there are lobbyists, one lobbyist-client pairing
			if 'staffer' in meeting:
				for s in meeting['staffer']: #one path per commissioner-staffer-lobby combination
					paths.append([meeting['commissioner'], s, lobbyists[(lobby)], lobby])
			else:
				paths.append([meeting['commissioner'], lobbyists[(lobby)], lobby]) #deal with case where lobbyists present but no staffers
		else:
			if 'staffer' in meeting:
				for s in meeting['staffer']:
					paths.append([meeting['commissioner'], s, lobby]) #case with staffer and no lobbyist
			else:
				paths.append([meeting['commissioner'], lobby]) #case with lobby, but neither staffers nor lobbyists
	for path in paths:
		add_path_wrapper(path, meeting, graphs, graph_id)


def get_commissioners(root_page):
	#returns the URIs for the current list of European Commissioners given the front page
	soup = soupify(root_page)	
	commissioners = []
	president = soup.find('div', {'class':'field-content member-details'})
	commissioners.append(president.a['href']) #right. they've added the list no fewer than three times in three tabs.
	#locate commissioners' details on page
	commissioner_block = soup.find('div', id="quicktabs-tabpage-team_members-0")
	members = commissioner_block.find_all('div', {'class':'field-content member-details'})
	for member in members:
		if member.find_next('span', {'class': 'term-39 In office label status'}).string == 'In office':
			#don't add any commissioners no longer in office
			commissioners.append(member.a['href'])
			#obtain their URI
	return commissioners

def get_commissioner_detail(commish, weightings):
	#returns details of a commissioner given their individual URI
	soup = soupify(commish)
	record = {}
	record['role'] = (soup.find('span', {'class':'role'})).string.strip()
	#gets commissioner's rank eg President, 1st VP, VP, Commish
	if record['role'] == u'High Representative':
		record['role'] = u'Vice-President' #the HR is a VP.
	record['name'] = (soup.find('span', {'class':'first-name'})).string.strip() + ' ' + (soup.find('span', {'class':'last-name'})).string.strip()
	if record['role'] != 'President': #it's not just blank for him, it's missing.
		record['job'] = (soup.find('span', {'class':'header-line-3'})).string.strip()
	else:
		record['job'] = record['role']
	#gets their department affiliation
	uris_block = soup.find('div', {'class': 'free-text'})
	uris_fns = uris_block.find_all('a')
	record['commish_meetings_uri'] = uris_fns[0]['href']
	#gets the URI for commissioners' meetings
	record['staff_meetings_uri'] = uris_fns[1]['href']
	#ditto for their staff
	#new_uri = commish.rstrip('_en') + '/team_en'
	if record['name'] == u'Andrus Ansip': #this is necessary because some sloppy herbert did the obvious
		link_name = u'team of ' + ' '+ (record['name'])
	elif 'Oettinger' in record['name']: #Oettinger wanted his initial but sysadmin didn't bother elsewhere
		link_name = u'team of ' + (record['name']).replace('H. ', '') #doing it this way to avoid PEP 263 whining.
	else:
		link_name = u'team of ' + (record['name'])
	print link_name
	new_uri = soup.find('a', title=link_name)['href']
	soup = soupify(new_uri)
	record['staffers'] = {}
	stf = soup.find_all('div', {'class':'member-details-text'}) #was field-content member-details
	for stfr in stf:
		staffer = {}
		if stfr.span.string != None: #Canetes fix. checks for presence of content
			try:
				stafferjob = (stfr.find('span', {'class':'label'})).string.strip()
				staffername = (stfr.find('span', {'class':'first-name'})).string.strip() + '' + (stfr.find('span', {'class':'last-name'})).string.strip()
				if stafferjob in weightings: #this check is here to deal with any weird job titles we didn't spot, also archivists and drivers, who some commissioners list.
					record['staffers'][(staffername)] = stafferjob #basically the same stuff for the staffers
			except AttributeError:
				pass
	return record

	
def meeting_parser(uri, details, lobbyists, graphs, staffers=None):
		print uri, staffers
		soup = soupify(uri)
		#gets meetings for a commissioner or staff member given output from get_commissioner_detail, parses them, and adds them to the networkx graph
		def inner_parser(uri, details, lobbyists, graphs, staffers=None):
			soup = soupify(uri)
			crufto = re.compile('[\t\r\n]|(  )') #strips cruft
			table = soup.find('table', id='listMeetingsTable')
			#pull the table
			for tr in table.tbody.find_all('tr'):
					if tr.td.string:
						strings = [list(td.stripped_strings) for td in tr.find_all('td')] 
                                                meeting = {}
						if staffers == None:
                                                        meeting['date'] = (strings[0])[0]               
                                                        meeting['locale'] = (strings[1])[0]
                                                        meeting['subject'] = (strings[3])[0]
							meeting['lobby'] = [re.sub(crufto, '', s) for s in strings[2]]
							meeting['job'] = details['role']
							meeting['dg'] = details['job']
							meeting['weight'] = float((get_weighting(meeting['dg'], meeting['job'], weightings))/len(meeting['lobby'])) #because we add a separate path for each lobbyist, got to do this. also reflects that a one-to-one is the ultimate platonic ideal of lobbying.	
						else:
						#meetings with staffers come as a package and include a name field. which can include multiple staffers.
                                                    	meeting['staffer'] = [(s.replace('  ', '')) for s in strings[0]]
                                                        meeting['date'] = (strings[1])[0]              
                                                        meeting['locale'] = (strings[2])[0]
                                                        meeting['lobby'] = [re.sub(crufto, '', s) for s in strings[3]]
                                                        meeting['subject'] = (strings[4])[0]
							meeting['job'] = [details['staffers'][(meeting[(staffer)])] for staffer in meeting['staffer']] 
							staffer_weights = [float(get_weighting(meeting['dg'], job, weightings)) for job in meeting['job']]	
							meeting['weight'] = float(sum(staffer_weights)/len(staffer_weights))
						if meeting['date'] != 'Cancelled': #this is a thing although check for tr.td.string should get it
							#parse the content into a row
							meeting['commissioner'] = details['name']
							meeting['lobbyists'] = [lobbyists[(l)] for l in meeting['lobby'] if l in lobbyists]
                                                        t = time.strptime(str(meeting['date']), '%d/%m/%Y')
							graph_id = time.strftime('./Graphs/%B%Y.json', t)
							#identify monthly graphs
							add_to_graph(meeting, graphs, graph_id, lobbyists)

	
		ll = soup.find('span', class_=re.compile('pagelinks|pagelinks ')) #yes. the span class "pagelinks" is sometimes "pagelinks" and sometimes "pagelinks " unsystematically. hence this wanky code.
		#page through the meetings, generating the URI for each page
		if ll:
			uribase = 'http://ec.europa.eu' + ll.a['href']
			for i in range(0, len(ll)):
				if i == 0:
					uri = uribase
				else:
					uri = uribase + str(i)
					
					print uri
				try:
					inner_parser(uri, details, lobbyists, graphs, staffers=None)
				except urllib2.HTTPError:
					print 'HTTP Error: ', uri
					return None
		else: #deal with single page case like Mogherini
			try:
				inner_parser(uri, details, lobbyists, graphs, staffers=None)
			except urllib2.HTTPError:
					print 'HTTP Error: ', uri
					return None
			#walk the pages
			

if 'Graphs' not in os.listdir('.'):
		os.mkdir('Graphs')

weightings = get_weighting_data(weighting_source)
lobbyclients = get_lobbyists_clients(lobbysource)
graphs = get_graphs()
commissioners = get_commissioners(root_page)

for commissioner in commissioners:
	details = get_commissioner_detail(commissioner, weightings)
	staff.append((details['staffers']).keys())
	meeting_parser(details['commish_meetings_uri'], details, lobbyclients, graphs)
	meeting_parser(details['staff_meetings_uri'], details, lobbyclients, graphs, staffers=True)
	
for graph in graphs.values():
	for n in graph.nodes(data=True):
		if 'type' not in n[1]:
			if n in staff:
				n[1]['type'] = 'staffer'
			elif n in lobbyclients.values():
				n[1]['type'] = 'lobbyist'
			elif n in lobbyclients:
				n[1]['type'] = 'lobby'
			else:
				n[1]['type'] = 'commissioner'
save_graphs(graphs)
