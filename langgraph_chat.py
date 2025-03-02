
from typing import (
    Any,
)
from abc import abstractmethod
from raphlib.graph import Graph, BaseState, interrupt
from raphlib import ToolCallEvent, ToolCallInitialization, ChatHistory
from langchain_core.messages import AIMessage, AIMessageChunk

import streamlit as st
from ._persistent_item import PersistentItem



class LangGraphChat(PersistentItem):
    """
    An interface on top of raphlib's LangGraph graphs.
    """
    def __init__(self):
        self.update = True
        self.graph = None
        self.create_graph()


    @abstractmethod
    def create_graph(self):
        """
        Reimplement this create_graph method in your subclass.
        """
        class State(BaseState):
            history: ChatHistory = ChatHistory()
            input_hint: str = "Write something..."
        self.graph = Graph[State]("node", state=State)
        raise NotImplementedError("You must implement the create_graph method in your subclass.")


    def display(self, height: int = None, border: bool = False):

        message_area = st.container(height=height, border=border)

        # Display messages from the history
        with message_area:
            for message in self.graph.state.history.messages:
                if message.type == "human":
                    with st.chat_message("human"):
                        st.markdown(message.content)
                elif message.type == "ai":
                    with st.chat_message("ai"):
                        st.markdown(message.content)

        if self.update:

            # Stream tool calls
            stream = self.graph.stream(self.update) if isinstance(self.update, str) else self.graph.stream()  # First run or not
            event = True
            spinner = "Running..."

            while event is not None:

                with st.spinner(spinner, show_time=True):

                    if isinstance(event, ToolCallInitialization):
                        spinner = f"Running {event.tool_name}"

                    elif isinstance(event, ToolCallEvent):
                        spinner = str(event.content)

                    elif isinstance(event, AIMessageChunk) and event.content:

                        def response_streaming():
                            yield event.content
                            for ev in stream:
                                if isinstance(ev, AIMessageChunk):
                                    yield ev.content
                                elif isinstance(ev, AIMessage):
                                    break  # Can be skipped safely
                                else:
                                    break  # Another tool is being run
                                    # raise ValueError(f"Unexpected event while streaming response : {type(ev)}")

                        with message_area: 
                            with st.chat_message("ai"):
                                st.write_stream(response_streaming)

                with st.spinner(spinner, show_time=True):

                    event = None
                    for event in stream: 
                        break

        # Display Chat Input
        self.update = st.chat_input(self.graph.state.input_hint, key=f"{self.key}_chat_input")
        if self.update:
            self.graph.state.history.append("human", self.update)
            st.rerun()



# ============================== EXAMPLE



class ExampleChat(LangGraphChat):
    """
    An example Chat widget.
    """
    def create_graph(self):
        class State(BaseState):
            history: ChatHistory = ChatHistory()
            input_hint: str = "Write something..."
        
        self.graph = Graph[State]("node", state=State)

        @self.graph.node(next="node")
        def node(s: State):
            interrupt("input")
            yield AIMessageChunk("Hello! How can I help you today?")
            s.history.append("ai", "Hello! How can I help you today?")
