	def make_unigraph_from_multigraph(self, mg=None): #you won't believe how cagy nx devs are about the fact a lot of their stuff doesn't work with multigraphs. anyway, this is some of their code.
		gg=nx.Graph()
		for n,nbrs in mg.adjacency_iter():
    			for nbr,edict in nbrs.items():
        			minvalue=min([d['weight'] for d in edict.values()])
        			gg.add_edge(n,nbr, weight = minvalue)
		return gg
