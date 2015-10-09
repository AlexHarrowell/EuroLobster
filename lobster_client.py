#!/usr/bin/python
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
from json import load, dump, dumps
from networkx.readwrite import json_graph
from networkx.algorithms import centrality, compose_all, link_prediction
from operator import itemgetter
import networkx as nx
import time
import os
import sys
import csv
import StringIO


#ok let's try to keep this focused. eventually this should be the basis for a flask web app so need to think routes.
#queries I can think of: 
#-name - searches for an individual and reports a bunch of stats. 
#-keyword_search reports stats for nodes having #keyword *keyword* in their attrs or edge attrs in their neighbourhood.
#-type and -month restrict the query - possible node types are lobbies, lobbyists, staffers, and commissioners. months are self explanatory. i hope.
#-stat restricts what metric gets returned. else return all.
#-directory lets you run this against stored graphs in some other dir should you so desire. people are strange.
#multiple entries for each are of course required.
#summary reports will be useful. eg top 10 for each group.'''

#'''what metrics do we want? weighted network degree, clearly. gatekeeper/flakcatcher (i.e average delta wnd of nodes in n.neighbours). centrality. greedy_fragile.'''

argparser = ArgumentParser()

e = sys.getfilesystemencoding()

argparser.add_argument('-n', '--name', type=lambda t: unicode(t, e), default=None)
argparser.add_argument('-m', '--month', type=lambda t: unicode(t, e), default=None)
argparser.add_argument('-k', '--keyword_search', type=lambda t: unicode(t, e), default=None)
argparser.add_argument('-s', '--stat', type=lambda t: unicode(t, e), default=None) 
argparser.add_argument('-o', '--output', type=lambda t: unicode(t, e), default='csv')
argparser.add_argument('-d', '--dir', type=lambda t: unicode(t, e), default='Graphs')
argparser.add_argument('-f', '--filename', type=lambda t: unicode(t, e), default=None)

#'''makes a simple command line interface'''
#'''usage: -n restricts which entities are returned, filtering on their names. accepts one name or a tab separated list. default: everyone. -m restricts return to provided month/year like so August2015. -k optionally permits you to search by one or more keywords.  this can also be used to restrict the search to lobbies/lobbyists/staffers/commissioners. -s restricts search to provided metric out of ['Closeness', 'Betweenness', 'Degree', 'Greedy_Fragile', 'Meetings', 'Link Centrality']. -d lets you specify where the graphs are kept. -o specifies output type - json or tab-separated values.'''

user_input = vars(argparser.parse_args())

class LobsterClient(object):
	def __init__(self, user_input):
		self.user_input = user_input

	def get_cache(self, directory):

	#'''because some of the algos are slow, we're caching a bunch of stuff and keeping it on disk for later. this looks for it and reutrns either a dict of cached information or an empty dict to receive it'''

		try:	
			with open(('./' + directory + '/lobster_cache')) as f:
				cache = load(f)
				return cache

		except (IOError, ValueError):
				
			cache = {}
			return cache

	def get_graphs(self):
	#'''walks through the directory where eurolobster stores scraped data, retrieving the graphs and inflating them'''
		graphs = {}
		filelist = os.walk(self.user_input['dir']).next()[2]
		for f in filelist:
			if '.json' in f:
				with open(('./' + (self.user_input['dir']) + '/' +  f)) as fo:
					try:
						g = json_graph.adjacency_graph(load(fo), multigraph=True)
						graphs[(f.strip('.json'))] = g
					except IOError:
						print 'not a Lobster graph: ', f
		return graphs


	def cacheflow(self, cache_key=str, data=None, remove=False):

	#'''provides caching'''

		if remove:
			del self.cache[cache_key]
		else:
			if data:
				self.cache[cache_key] = data
				with open(('./' + (self.user_input['dir']) + '/lobster_cache'), 'a+') as f:
					try:
						cache = load(f)
					except ValueError: #no cached data exists
						cache = {}
					cache.update(self.cache)
					f.truncate()
					dump(cache, f)
			else:
					return None

	def network_wide_centrality(self, months):

	#'''computes the network-wide centrality, ie. average of betweenness centrality for all nodes in each monthly network. this is needed for GREEDY_FRAGILE, and is a pain to compute. so we do it at startup, cache it, and keep it on disk.'''
		result = {}
		for m in months:
			ck = u'nwc' + m
			if ck in self.cache:
				return self.cache[ck]
			else:
				result[m] = centrality.betweenness_centrality(self.graphs[m], weight='weight')
				self.cacheflow(cache_key=ck, data=result)
	
	def make_unigraph_from_multigraph(self, mg=None): #you won't believe how cagy nx devs are about the fact a lot of their stuff doesn't work with multigraphs. anyway, this is some of their code.
		gg=nx.Graph()
		for n,nbrs in mg.adjacency_iter():
    			for nbr,edict in nbrs.items():
        			minvalue=min([d['weight'] for d in edict.values()])
        			gg.add_edge(n,nbr, weight = minvalue)
		return gg

	def greedy_fragile(self, graph, nedges, month):
		nodes = self.cache[(u'nwc' + month)][month]
		nwc = float(sum(nodes.values())/len(nodes.values()))
		total_centrality = (graph.order()) * nwc
		result = {}
		if nedges == None:
			nedges = graph.nodes()
		for n in nedges:
			neigh = [n for n in graph.neighbors(n) if len(graph.neighbors(n)) > 0]
			neigh_central = sum([v for k,v in nodes.iteritems() if k in neigh])  
			order = graph.order() - (1 + len(neigh))
			mc = nodes[n] + neigh_central
			gf = nwc - ((total_centrality - mc)/order)
			result[n] = gf
		return result


	def get_metric_from_graph(self, metric=None, nedges=None, keyword=None, graph=None, month=None):

	#'''this func will do most of the work. lets you get a named metric for nodes, optionally restricting this by month, by specified nodes, or by entity type ie lobby/staffer/lobbyist/commissioner. first constructs a cache key and then looks in the cache

		ck = str(metric) + str(month) + str(keyword)
		if ck in self.cache:
			return self.cache[ck]

		g = graph
		if keyword:
			nedges = [node[0] for node in g.nodes_iter(data=True) if node[1]['type'] == keyword]
		#'''if a keyword search is specified, we list the nodes where that keyword is found in one of its attributes'''
		
		if metric == u'Degree':		
			#gr = self.make_unigraph_from_multigraph(mg=g)			
			upshot = g.degree(nbunch=nedges)

		if metric == u'Closeness Centrality':
			#g = self.make_unigraph_from_multigraph(mg=g)
			#for e in g.edges_iter(data=True):
				#print e
			u = centrality.closeness_centrality(g, normalized=True)
			if nedges:
				upshot = {k: v for k,v in u.items() if k in nedges}
			else:
				upshot = u

		if metric == u'Betweenness':
                        u = centrality.betweenness_centrality(g, weight='weight', normalized=True)	
			if nedges:
				upshot = {k: v for k,v in u.items() if k in nedges}
					#[k for k in u if k[0] in nedges]
			else:
				upshot = u

		if metric == u'Greedy_Fragile':
			upshot = self.greedy_fragile(g, nedges, month)

		if metric == u'Link Centrality':
			u = centrality.edge_betweenness_centrality(g, weight='weight', normalized=True)
			if nedges:
				upshot = {unicode(k[0] + ' ,' + k[1]): v for k,v in u.items() if k in nedges}
			else:
				upshot = u

		if metric == u'Predicted Links':
			gr = self.make_unigraph_from_multigraph(g)
			u = link_prediction.resource_allocation_index(gr)
			upshot = {} #[]
			for k, v in u.items():
				if v > 0: #RAI examines all nonexistent edges in graph and will return all of them, including ones with a zero index. we therefore filter for positive index values. 
					if nedges:
						if k[0] in nedges or k[1] in nedges:
							upshot[(k[0], k[1])] = v
					else:
						upshot[(k[0], k[1])] = v
		self.cacheflow(ck, data=upshot)
		return upshot
		#return sorted(upshot, key=itemgetter(1))
			
                
	def LobsterClient(self):
		self.cache = self.get_cache(self.user_input['dir'])
		self.graphs = self.get_graphs()
		if self.user_input['name']:
			names = [s.strip() for s in self.user_input['name'].split('/t')]
		else:
			names = None

		if self.user_input['month']:
			month = [m.strip() for m in self.user_input['month'].split('/t')] #changed here to convert input to unicode and avoid having to take python objects as input, while supporting multiple-input queries.
			months_to_get = sorted(month, key=lambda s: time.strptime(s, '%B%Y'))
		else:
			months_to_get = sorted(self.graphs.keys(), key=lambda s: time.strptime(s, '%B%Y'))

		self.nwc = self.network_wide_centrality(months_to_get)
		new_graph = nx.MultiGraph(weighted=True)
		output = {}
		ks = []
		for m in months_to_get:
			new_graph.add_nodes_from(self.graphs[m].nodes_iter(data=True))
			new_graph.add_weighted_edges_from(self.graphs[m].edges_iter(data=True))
			output[m] = self.get_metric_from_graph(metric=self.user_input['stat'], nedges=names, keyword=self.user_input['keyword_search'], graph=new_graph, month=m)	
			ks.extend(output[m].keys())
		kset = set(ks)
		outkeys = sorted(output.keys(), key=lambda s: time.strptime(s, '%B%Y'))
		ok = outkeys[:]
		ok.insert(0, 'name')
		if self.user_input['output'] == u'csv':
			if self.user_input['filename']:
				with open(self.user_input['filename'], 'w') as f:
					c = csv.DictWriter(f, fieldnames=ok)
					c.writeheader()
					for k in ks:
						row = {m: output[m].get(k, 0) for m in outkeys}
						row['name'] = k.encode('utf-8')
						c.writerow(row)
			else:
				s = StringIO.StringIO()
				c = csv.DictWriter(s, fieldnames=ok)
				c.writeheader()
				for k in ks:
					row = {m: output[m].get(k, 0) for m in outkeys}
					row['name'] = k.encode('utf-8')
					c.writerow(row)
				print s.getvalue()
				s.close()
				

		elif self.user_input['output'] == u'json':
			if self.user_input['filename']:
				with open(self.user_input['filename'], 'w') as f:
					outlist = []
					for k in ks:
						row = {m: output[m].get(k, 0) for m in outkeys}
						row['name'] = k
						outlist.append(row)
					dump(outlist, f)
			else:
				outlist = []
				for k in ks:
					row = {m: output[m].get(k, 0) for m in outkeys}
					row['name'] = k
					outlist.append(row)
				s = dumps(outlist)
				print s				

lc = LobsterClient(user_input)
lc.LobsterClient()


