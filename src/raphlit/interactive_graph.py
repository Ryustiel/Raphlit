"""
A generic graph class that can be used with streamlit.
Manages persistent states and a couple useful events.
"""

from typing import (
    Any,
    List, 
    Dict,
    Callable,
    Optional, 
    Tuple,
)
from pydantic import BaseModel
from abc import abstractmethod

import streamlit as st

from ._persistent_item import PersistentItem
from .rerun_flag import set_rerun_flag
from streamlit_plotly_events import plotly_events

import random
import networkx as nx
import plotly.graph_objects as go



# ================================================================ NODE MODELS



class NodeConfig(BaseModel):
    color: str = "gray"
    size: float = 10.0

class EdgeConfig(BaseModel):
    color: str = "#888"
    width: float = 1.0

class Node(BaseModel):
    """Stores information about a node."""
    external_id: Any  # This is used for referring to nodes in functions and llm tools
    label: str
    hover: str
    value: Any
    config: NodeConfig

class Edge(BaseModel):
    """Stores information about an edge."""
    config: EdgeConfig
    start: int
    end: int

class GraphItems(BaseModel):
    """Stores items for the graph."""
    nodes: List[Node] = []
    edges: List[Edge] = []

    node_config: Dict[str, NodeConfig] = {}
    edge_config: Dict[str, EdgeConfig] = {}

    def add_node_config(self, name: str, config: NodeConfig):
        self.node_config[name] = config

    def add_edge_config(self, name: str, config: EdgeConfig):
        self.edge_config[name] = config

    def add_node(self, external_id: str, value: Any, config: str, label: str= "", hover: str = ""):
        self.nodes.append(Node(external_id=external_id, label=label, hover=hover, value=value, config=self.node_config[config]))

    def add_edge(self, start: str, end: str, config: str):  # Start and End are external ids
        self.edges.append(Edge(config=self.edge_config[config], start=self.get_node_id(start), end=self.get_node_id(end)))

    def get_node(self, local_id: int):
        return self.nodes[local_id]
    
    def get_node_id(self, external_id: Any):
        for i, node in enumerate(self.nodes):
            if node.external_id == external_id:
                return i
        raise ValueError(f"No node with external_id {external_id}")



# =============================================================================== GRAPH



class InteractiveGraph(PersistentItem):
    """
    Base class for graph components.
    Manages persistent state, caching, and common graph operations.
    """

    def __init__(self, on_select: List[Callable[[Any, str], None]] = [], graph_items: GraphItems = None):
        """
        Initializes the on_select and the graph_items when no node is selected.
        """
        super().__init__()

        self.on_select = on_select
        self.graph_items = graph_items or GraphItems()
        self.figure: go.Figure = None
        
        self.selected_values: List[Any] = None  # This one remains valid across reruns
        self.selected_external_ids: List[Any] = None

        self._update: bool = True  # Triggers update event after the graph is rerun

        # This one is solely used for handling the user click events with the plotly_events widget
        self._cached_plotly_selection: Optional[List[Dict[str, Any]]] = None
        
    # ================================================================== SUBCLASS INTERFACE

    @abstractmethod
    def build_nodes(self, *args, **kwargs):
        """
        Create the graph's item set (nodes and edges).
        Typically called in self.selection_event().
        Can depend on external input for selecting which nodes and edges to display.
        """
        raise NotImplementedError("Subclasses must implement build_nodes(), which sets the graph_items property.")

    @abstractmethod
    def on_update(self):
        """
        This is run once every time a new node has been selected and the graph has been rerun.
        This typically rebuild the nodes and recompute the figure.
        """
        raise NotImplementedError("Subclasses must implement on_update(), which recomputes the graph every time a new node is selected")

    # ================================================================== INTERACTION AND DISPLAY LOGIC

    def display(self, height=650):
        """
        Displays the graph and process click events.
        """
        plotly_key = self.key + "_plotly_figure"

        if self._update:
            self.on_update()
            self._update = False
            # self._cached_plotly_selection = None
            # st.session_state[plotly_key] = None

        selected_points = self.process_plotly_selection(
            plotly_events(
                plot_fig=self.figure,
                click_event=True,
                key = plotly_key,
                override_height=height,
            )
        )

        if selected_points:
            self.select_node(selected_points, rerun=True)

    def process_plotly_selection(self, plotly_selection: List[Dict[str, Any]] | None) -> Optional[List[int]]:
        """
        Handles the value of the plotly_events widget.
        If the value was updated, causes an update to the graph.
        """
        if plotly_selection:
            if (
                self._cached_plotly_selection is None
                or plotly_selection[0]["pointNumber"] != self._cached_plotly_selection[0]["pointNumber"]
            ):
                self._cached_plotly_selection = plotly_selection
                return [plotly_selection[0]["pointNumber"]]
        return None

    def select_node(
            self, 
            ids: int | List[int] | None = None,
            external_ids: Any | List[Any] | None = None, 
            event: str = "default", 
            ignore_current: bool = False,
            rerun: bool = False
        ):
        """
        Select the node on the graph and refresh it.
        If you use this function outside the graph you should schedule the rerun however suits you.

        Parameters:
            ids (List[int], int, None): 
                The ids of the nodes to select.
                Setting both ids and external_ids to None deselects all.
            external_ids (List[Any], Any, None):
                The external ids of the nodes to select.
            event (str):
                The event that triggered the selection.
            ignore_current (bool):
                Whether to ignore the current selection.
                If True, selection event is triggered 
                even is the new selection is the same as the current.
            rerun (bool):
                Whether this function should set the streamlit rerun flag.
                This parameter is intended for internal use.
        """
        if external_ids is not None:
            if ids is not None:
                raise ValueError("Cannot provide both ids and external_ids")
            if isinstance(external_ids, str):
                external_ids = [external_ids]
            ids = [self.graph_items.get_node_id(external_id=external_id) for external_id in external_ids]
        else:
            if isinstance(ids, int):
                ids = [ids]

        nodes = [self.graph_items.get_node(node_id) for node_id in ids] if ids is not None else []
        self.selected_values = [node.value for node in nodes] if nodes else []
        external_ids = [node.external_id for node in nodes] if nodes else []
    
        if self.selected_external_ids != external_ids or ignore_current:  # Worth updating the graph
        
            self.selected_external_ids = external_ids
            self._update = True

            for callback in self.on_select:
                callback(self.selected_values, event)

            if rerun:
                set_rerun_flag()

    def compute_figure(self, 
            figure_height: int = 600,
            node_trace_mode: str = "markers+text",
            layout: Callable[[nx.DiGraph], List[Tuple[float, float, float]]] = None,
        ) -> go.Figure:
        """
        Compute a plotly figure from the values of self.graph_items.

        Parameters:
            figure_height (int): 
                Height of the plotly figure
            node_trace_mode (str): 
                The trace mode for the Node. 
                See plotly's scatter 3D for more information.
            layout (Callable[[nx.DiGraph], List[Tuple[float, float, float]]]):
                A function that produces coordiniates for each node in a networkx digraph structure.
                Defaults to networkx' spring_layout with a random seed.
        """
        layout = layout or (lambda digraph: [pos for id, pos in nx.spring_layout(digraph, dim=3, seed=random.randint(1, 10^3)).items()])

        # Compute node positions
        positioning: nx.DiGraph = nx.DiGraph()

        for i, node in enumerate(self.graph_items.nodes): positioning.add_node(i)
        for edge in self.graph_items.edges: positioning.add_edge(edge.start, edge.end)

        positions: List[Tuple[int, int, int]] = layout(positioning)

        # Build the figure
        fig = go.Figure()
        node_x, node_y, node_z = [], [], []
        node_colors, node_sizes, node_labels, node_hover = [], [], [], []

        # Unpacking
        for node, pos in zip(self.graph_items.nodes, positions):
            node_x.append(pos[0])
            node_y.append(pos[1])
            node_z.append(pos[2])
            node_colors.append(node.config.color)
            node_sizes.append(node.config.size)
            node_labels.append(node.label)
            node_hover.append(node.hover)

        node_trace = go.Scatter3d(
            x=node_x,
            y=node_y,
            z=node_z,
            mode=node_trace_mode,
            marker=dict(
                size=node_sizes,
                color=node_colors,
                line=dict(width=0.5),
            ),
            text=node_labels,
            textposition="top center",
            hoverinfo='none',
            customdata=node_hover,
            hovertemplate='<b>%{customdata}</b><extra></extra>',
            name='Nodes'
        )
        for edge in self.graph_items.edges:
            x0, y0, z0 = positions[edge.start]
            x1, y1, z1 = positions[edge.end]
            fig.add_trace(go.Scatter3d(
                x=[x0, x1, None],
                y=[y0, y1, None],
                z=[z0, z1, None],
                mode='lines',
                line=dict(width=edge.config.width, color=edge.config.color),
                hoverinfo='none',
                showlegend=False
            ))
        fig.add_trace(node_trace)
        fig.update_layout(
            scene=dict(
                xaxis=dict(showbackground=False, showticklabels=False, visible=False),
                yaxis=dict(showbackground=False, showticklabels=False, visible=False),
                zaxis=dict(showbackground=False, showticklabels=False, visible=False),
            ),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color="white"),
            height=figure_height,
            margin=dict(l=0, r=0, b=0, t=0),
            showlegend=False,
        )
        return fig




# ====================================================================== EXAMPLE




class ExampleInteractiveGraph(InteractiveGraph):
    """
    A minimal subclass of GraphComponent.

    This example implementation creates a simple graph with two nodes and one edge,
    and processes node selection by storing the selected node's label.
    """
    def __init__(self):
        super().__init__(on_select=[])  # Define callbacks

    def build_nodes(self) -> GraphItems:

        items = GraphItems(
            node_config = {
                "default": NodeConfig(color="orange", size=20),
                "selected": NodeConfig(color="red", size=30),
            },
            edge_config = {
                "default": EdgeConfig(width=5),
                "selected": EdgeConfig(width=10),
            }
        )
        items.add_node("A", value="A Value", label="A", config="selected" if self.selected_external_ids and self.selected_external_ids[0] == "A" else "default")
        items.add_node("B", value="B Value", label="B", config="selected" if self.selected_external_ids and self.selected_external_ids[0] == "B" else "default")
        items.add_node("C", value="C Value", label="C", config="selected" if self.selected_external_ids and self.selected_external_ids[0] == "C" else "default")
        items.add_edge("A", "B", config="selected" if self.selected_external_ids and (self.selected_external_ids[0] == "A" or self.selected_external_ids[0] == "B") else "default")

        return items

    def on_update(self):
        with st.spinner("Fetching nodes..."): 
            self.graph_items = self.build_nodes()
        self.figure = self.compute_figure()



def display_interactive_graph_example():

    graph = ExampleInteractiveGraph.st("interactive_graph_example")
    graph.display()
    
    if graph.selected_values:
        st.write(graph.selected_values)
