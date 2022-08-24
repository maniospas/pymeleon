from language.rule import Rule
from viewer.genetic_viewer import GeneticViewer
import pygrank as pg
import networkx as nx
from language.language import Language
from pymeleon import parse

def list2dict(x: list):
    return {v: 1 for v in x}
    
G = nx.Graph()
G.add_edge("a232", "b232")
x = ["a232"]

viewer = Language(
    Type("normalized": lambda x: pg.max(x) == 1),
    Rule(parse(pg.GraphSignal), parse("_.graph": nx.Graph)),
    Rule(parse(list), parse("list2dict(_)", {"list2dict": ("normalized", dict)})),
    Rule(parse({"a": nx.Graph, "b": dict}), parse("pg.to_signal(a, b)", {"pg.to_signal": ("normalized", "noinput", pg.GraphSignal)})),
) >> GeneticViewer({"list2dict": list2dict, "pg": pg})

result = viewer(G, x) >> parse("OUT", "GraphSignal")
print(result)
