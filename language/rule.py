"""
Rule module for pymeleon
"""
from copy import deepcopy
from language.parser import Node
from collections import defaultdict

class BadGraph(Exception):
    """
    Invalid graph input Exception
    """
    pass
    
class Rule:
    """
    Rule object for graph transformation
    
    -- Parameters --
        parser_obj_in: the parser object representing the graph that the rule can be applied to
        parser_obj_out: the parser object representing the graph after the application of the rule
    
    -- Attributes --
        node_dict: dictionary mapping nodes from the generic input graph to the generic output graph (1-n)
        reverse_node_dict: dictionary mapping nodes from the generic output graph to the generic input graph (1-1)
        
    -- Methods --
        apply(graph): applies the rule to the specified graph
    """
    
    def __init__(self, parser_obj_in, parser_obj_out):
        self._parser_obj_in = parser_obj_in
        self._parser_obj_out = parser_obj_out
        
        self._graph_in = parser_obj_in.graph
        self._obj_in = parser_obj_in.variables_constants
        self._funcs_in = parser_obj_in.functions
        self._constraints = parser_obj_in.constraints
        
        self._graph_out = parser_obj_out.graph
        self._obj_out = parser_obj_out.variables_constants
        self._funcs_out= parser_obj_out.functions

        self._create_node_dict()
        
    def _create_node_dict(self):
        node_dict = dict()
        reverse_node_dict = dict()
        graph_in_node_dict = dict()
        # Python dictionaries are ordered since 3.7, so the first element will always be "root_node"
        for node in tuple(self._graph_in.nodes)[1:]:
            graph_in_node_dict[node.value] = node
        common_obj = self._obj_in & self._obj_out
        unmatched_nodes = list(self._graph_out.nodes)[1:]
        for obj in common_obj:
            obj_nodes = []
            for node in unmatched_nodes:
                if node.value == obj:
                    reverse_node_dict[node] = graph_in_node_dict[obj]
                    obj_nodes.append(node)
            node_dict[graph_in_node_dict[obj]] = list(obj_nodes)
            for node in obj_nodes:
                unmatched_nodes.remove(node)
        self.node_dict = node_dict
        self.reverse_node_dict = reverse_node_dict
    
    def _copy_apply_graph(graph):
        """
        Returns a deepcopy of the graph and the new transform_node_dict
        """
        pass

    def _remove_mapped_edges_rec(self, node):
        cur_transform_dict = self._cur_transform_dict
        for successor_node in self._graph_in.successors(node):
            self._cur_graph.remove_edge(cur_transform_dict[node], cur_transform_dict[successor_node])
            self._remove_mapped_edges_rec(successor_node)

    def _copy_output_node(self, node):
        """
        Returns a copy of a node in the generic output graph with the value required for the application of the rule
        """
        reverse_node_dict = self.reverse_node_dict
        if node in reverse_node_dict:
            node_copy = Node(self._cur_transform_dict[reverse_node_dict[node]].value)
            self._cur_node_dict[reverse_node_dict[node]].append(node_copy)
        else:
            node_copy = Node(node.value)
        return node_copy

    def _add_output_graph_rec(self, root_node, root_node_copy):
        graph_out = self._graph_out
        for node in graph_out.successors(root_node):
            node_copy = self._copy_output_node(node)
            self._cur_graph.add_edge(root_node_copy, node_copy, order=graph_out.get_edge_data(root_node, node)["order"])
            self._add_output_graph_rec(node, node_copy)

    def _add_output_graph(self):
        """
        Add a copy of the output graph to the currently under transformation graph and create the specific _cur_node_dict
        """
        self._cur_node_dict = defaultdict(list)
        for node in self._graph_out.successors("root_node"):
            node_copy = self._copy_output_node(node)
            if node not in self.reverse_node_dict:
                self._cur_graph.add_edge("root_node", node_copy, order=-1)
            self._add_output_graph_rec(node, node_copy)

    def apply(self, graph, transform_node_dict, deepcopy_graph=False):
        """
        Apply the rule to the specified graph

        -- Arguments --
            graph (networkx DiGraph): the graph to transform
            transform_node_dict (dict): dictionary mapping each node in the generic input graph to each node in the graph to be transformed
            deepcopy_graph (bool): if True, the graph will be deepcopied before the transformation and returned after it
                                   if False, the graph will be transformed in place
        
        -- Returns --
            transformed_graph (networkx DiGraph): the transformed graph
        """
        reverse_transform_dict = dict((v, k) for k, v in transform_node_dict.items())
        if deepcopy_graph:
            graph, transform_node_dict = self._copy_apply_graph(graph)
        self._cur_graph = graph
        self._cur_transform_dict = transform_node_dict

        # Remove the edges that make up the structure of the generic input graph
        for in_node in self._graph_in.successors("root_node"):
            self._remove_mapped_edges_rec(in_node)

        self._add_output_graph()
        cur_node_dict = self._cur_node_dict

        # Remove the nodes that were transformed and add between the new output nodes and the rest of the graph any edges that
        # existed between nodes that were transformed (and mapped to output nodes) and the rest of the graph
        for graph_node in reverse_transform_dict:
            if graph_node in cur_node_dict:
                out_nodes = cur_node_dict[graph_node]
                num_out_nodes = len(cur_node_dict[graph_node])
                for pre_node in graph.predecessors(graph_node):
                    if pre_node not in reverse_transform_dict:
                        cur_order = graph.get_edge_data(pre_node, graph_node)["order"]
                        # out_edges with data=True returns a tuple of (pre_node, suc_node, {attribute_keys: attribute_values})
                        # The following code ensures that order is preserved
                        for edge in graph.out_edges(pre_node, data=True):
                            if edge[2]["order"] > cur_order:
                                edge[2]["order"] += num_out_nodes - 1
                        for i, node in enumerate(out_nodes):
                            graph.add_edge(pre_node, node, order=cur_order + i)
                for suc_node in graph.successors(graph_node):
                    if suc_node not in reverse_transform_dict:
                        for node in cur_node_dict[graph_node]:
                            graph.add_edge(node, suc_node, order=graph.get_edge_data(graph_node, suc_node)["order"])
                graph.remove_node(graph_node)
            else:
                # Fix this part
                if graph.out_degree(graph_node) == 0:
                    if graph.in_degree(graph_node) == 0 or "root_node" in graph.predecessors(graph_node):
                        # Remove any nodes from the transformation dict that have total degree 0 (or are connected to the root node and 
                        # have out_degree == 0) and do not correspond to nodes in the generic output graph
                        graph.remove_node(graph_node)

        if deepcopy_graph:
            return graph

class RuleSearch:
    pass