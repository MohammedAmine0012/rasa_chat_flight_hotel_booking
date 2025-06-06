from typing import Any, Dict
import pytest
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from actions.actions import ActionSearchFlights, ActionSearchHotels

@pytest.fixture
def dispatcher():
    return CollectingDispatcher()

@pytest.fixture
def tracker():
    return Tracker("default", {}, {}, [], False, None, {}, "action_listen")

def test_search_flights(dispatcher, tracker):
    action = ActionSearchFlights()
    tracker.slots["ville_depart"] = "الدار البيضاء"
    tracker.slots["ville_destination"] = "باريس"
    tracker.slots["date_depart"] = "2023-12-01"
    tracker.slots["classe"] = "اقتصادية"

    result = action.run(dispatcher, tracker, {})
    
    assert result is not None
    assert "flight_details" in result[0]
    assert "search_completed" in result[1]

def test_search_hotels(dispatcher, tracker):
    action = ActionSearchHotels()
    tracker.slots["ville_hotel"] = "مراكش"
    tracker.slots["nombre_personnes"] = 2

    result = action.run(dispatcher, tracker, {})
    
    assert result is not None
    assert "hotel_details" in result[0]
    assert "search_completed" in result[1]