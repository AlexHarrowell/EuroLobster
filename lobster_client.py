#!/usr/bin/python

from argparse import ArgumentParser

'''ok let's try to keep this focused. eventually this should be the basis for a flask web app so need to think routes.
queries I can think of: 
-name - searches for an individual and reports a bunch of stats. 
-keyword_search reports stats for nodes having #keyword *keyword* in their attrs or edge attrs in their neighbourhood.
-type and -month restrict the query - possible node types are lobbies, lobbyists, staffers, and commissioners. months are self explanatory. i hope.
-stat restricts what metric gets returned. else return all.
-directory lets you run this against stored graphs in some other dir should you so desire. people are strange.
multiple entries for each are of course required.
summary reports will be useful. eg top 10 for each group.'''

'''what metrics do we want? weighted network degree, clearly. gatekeeper/flakcatcher (i.e average delta wnd of nodes in n.neighbours). centrality. greedy_fragile. any others? distance from JCJ?'''

argparser = ArgumentParser()

argparser.add_argument('-n', '--name', type=str,list)
argparser.add_argument('-t', '--type', type=str,list)
argparser.add_argument('-m', '--month', type=str,list)
argparser.add_argument('-k', '--keyword_search', type=str,list)
argparser.add_argument('-s', '--stat', type=str,list) 
argparser.add_argument('-d', '--dir', type=str, default='Graphs')

class LobsterClient():
	def _init_(self, user_input):
		self.user_input = vars(argparser.parse_args())
		self.graphs = get_graphs(user_input['dir'])
		self.cache = {}

	def get_graphs():
		graphs = {}
		fs = (os.walk(user_input['dir']).next())[2]
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

	def cacheflow(cache_key=str, data={}, remove=False):
		if remove:
			del self.cache[(cache_key)]
		else:
			if data:
				self.cache[(cache_key)] = data
			else:
				if cache_key in self.cache:
					return self.cache[(cache_key)]
				else:
					return None

	def get_metric_from_graph(graph=list, metric=None, node=None, entitytype=None):
		key = (node + graph + metric)
		c = cacheflow(cache_key=key)
		if c:
			return c 
		else:
			if len(graph) == 1:				
				graphs_reqd = self.graphs[(graph[0])]
			else:
				graphs_reqd = [(g,self.graphs[(g)]) for g in graph]  
			if node:
				nodes_to_get = [n for n in node]
			if metric:
				mtg = [m for m in metric]
			response = {}
			for g in graphs_reqd:
				if 
					
