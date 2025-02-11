from typing import Callable, List
from enum import Enum


class FocusState(Enum):
    FOCUSED = "focused"
    UNFOCUSED = "unfocused"


class SharedState:
    _instance = None
    _focus_state: FocusState = FocusState.UNFOCUSED
    _focus_handlers: List[Callable[[FocusState], None]] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SharedState, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_focus_state(cls) -> FocusState:
        return cls._focus_state

    @classmethod
    def set_focus_state(cls, state: FocusState):
        cls._focus_state = state
        # Notify all handlers of state change
        for handler in cls._focus_handlers:
            handler(state)

    @classmethod
    def add_focus_handler(cls, handler: Callable[[FocusState], None]):
        cls._focus_handlers.append(handler)

    @classmethod
    def remove_focus_handler(cls, handler: Callable[[FocusState], None]):
        if handler in cls._focus_handlers:
            cls._focus_handlers.remove(handler)

    @classmethod
    def is_focused(cls) -> bool:
        return cls._focus_state == FocusState.FOCUSED


