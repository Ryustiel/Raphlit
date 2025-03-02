from typing import Optional, Type, TypeVar, cast
from abc import abstractmethod, ABC

import streamlit as st

T = TypeVar('T', bound='PersistentItem')

class PersistentItem(ABC):
    """
    A streamlit value that can persist and be displayed.
    """
    @property
    def key(self) -> str:
        if hasattr(self, '_key'):
            key = getattr(self, '_key', None)
            if isinstance(key, str):
                return key
        raise LookupError("""
            The key was not set for this persistant item. 
            Key is set automatically when a persistant item is instanciated via a PersistentItem method such as .st() or .persist()
            You can bypass this by not using the .key property which is a computed property.
        """)

    @classmethod
    def get_from_session(cls: Type[T], key: str) -> T:
        """Retrieve an instance of this class from the session state."""
        item = st.session_state.get(key)
        if cls.__name__ != type(item).__name__:
            raise ValueError(f"Expected {cls.__name__}, got {type(item).__name__}")
        return item

    @classmethod
    def st(cls: Type[T], key: str, initial_value: Optional[T] = None, check_persistence: bool = True, **kwargs) -> T:
        """Retrieve an instance of this class from the session state."""
        if check_persistence:
            cls.persist(key=key, initial_value=initial_value, **kwargs)
        return cls.get_from_session(key=key)

    @classmethod
    def set_session(cls: Type[T], key: str, value: T) -> None:
        """Sets the value of the instance at {key} in the session state to the provided one"""
        setattr(value, '_key', key)  # Store the key as an attribute of the persistant item
        st.session_state[key] = value

    @classmethod
    def persist(cls: Type[T], key: str, initial_value: Optional[T] = None, rebuild_on_reload: bool = False, **kwargs) -> None:
        """
        Store an instance of this object in the session state if one does not exist already, to be accessed later.
        NOTE : rebuild_on_reload = True will cause the instance to be reinstantiated every time streamlit reloads.
        """
        if key not in st.session_state or rebuild_on_reload:
            if initial_value is None:
                cls.set_session(key=key, value=cls(**kwargs))  # Use default constructor
            else:
                cls.set_session(key=key, value=initial_value)
