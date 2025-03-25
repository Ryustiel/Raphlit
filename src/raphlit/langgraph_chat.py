
from typing import (
    Any,
    Generator,
)
from abc import abstractmethod
from raphlib.graph import Graph, BaseState, interrupt
from raphlib import ToolCallStream, ToolCallInitialization, ChatHistory
from langchain_core.messages import AIMessage, AIMessageChunk

import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from ._persistent_item import PersistentItem



class LangGraphChat(PersistentItem):
    """
    An interface on top of raphlib's LangGraph graphs.
    """
    def __init__(self):
        self.update = True
        self.graph = None
        self.chat_icons = {}  # A mapping of message from the message history to an icon
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
    
    def process_event(self, event: Any, stream: Generator[Any, None], message_area: DeltaGenerator):
        """
        Process an event from the stream.
        """
        if isinstance(event, AIMessageChunk) and event.content:

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
                with st.chat_message("ai", avatar = self.chat_icons.get("ai", None)):
                    st.write_stream(response_streaming)


    def display(self, height: int = None, border: bool = False):

        message_area = st.container(height=height, border=border)

        # Display messages from the history
        with message_area:
            for message in self.graph.state.history.messages:
                with st.chat_message(message.type, avatar = self.chat_icons.get(message.type, None)):
                    st.markdown(message.content)

        if self.update:

            # Stream tool calls
            stream = self.graph.stream(self.update) if isinstance(self.update, str) else self.graph.stream()  # First run or not
            event = True

            while event is not None:

                self.process_event(event, stream=stream, message_area=message_area)

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
