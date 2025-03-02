
from typing import (
    List,
    Optional,
)
from pydantic import BaseModel
from abc import abstractmethod, ABC

from ._persistent_item import PersistentItem
import streamlit as st

class PydanticForm(BaseModel, PersistentItem):
    """
    A form that will persist in the session state through a pydantic model.
    An instance of this model can be edited at any point in the code and the changes will be reflected in the form.
    """
    
    def update(self, *args, **kwargs):
        """
        Update the form with the given keyword arguments or (non keyword) instance of the current model to update from.
        """
        if args:
            if len(args) > 1:
                raise ValueError("Too many positional arguments. There can be only one argument.")
            elif not isinstance(args[0], BaseModel):
                raise ValueError("Non keyword argument should be a PydanticForm.")
            else:
                self.update(**args[0].model_dump(exclude_unset=True))
        else:
            for key, value in kwargs.items():
                setattr(self, key, value)

    def update_from_model(self, instance: 'PydanticForm'):
        """
        Update the form with the values from the given model instance.
        """
        if not isinstance(instance, self.__class__):
            raise ValueError(f"Instance of class {type(instance)} does not have the expected input type")
        self.update(**instance.model_dump(exclude_unset=True))
    
    def display(self) -> 'PydanticForm':
        """
        Display the form with the current values as defaults.
        Also maps them to this model's value so that the changes are reflected in the session_state.
        
        Example :
            self.field1 = st.text_input('Write here', value=self.field1)
        """
        raise NotImplementedError("Implement the display method to define which streamlit components will be created, and in which value(s) of the pydantic model their contents will be stored.")

    def commit(self):
        """
        Commit the changes made in the form to the model.
        NOTE : This method is not implemented by default.
        """
        raise NotImplementedError("If using the form's commit method you must implement it. Otherwise, code the commit behavior directly in the page.")
    
    def delete(self):
        """
        Delete the form from the session state.
        """
        raise NotImplementedError("Implement the delete method to remove the form from the session state.")

    def __call__(self) -> 'PydanticForm':
        return self.display()
