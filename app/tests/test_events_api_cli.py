# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Manual API endpoint test script for the Nextcloud CalDAV events FastAPI app.

Results are printed to stdout for manual inspection.
"""

import json
import uuid
import sys
from datetime import datetime, timedelta

from .support.events_client import EventsApiClient

def isoformat_seconds(dt: datetime) -> str:
    """
    Format a datetime value to match the Events API requirements (second precision).
    """
    return dt.strftime("%Y-%m-%dT%H:%M:%S")

TEST_TIMEZONE = "Europe/Paris"
events_client = EventsApiClient()

""" TESTING API ENDPOINTS """

def run_get_event_by_uid(event_uid=None, is_debug=False):
    """Test the GET /events/{uid} endpoint to retrieve a single event by UID."""
    # If no event UID is provided, use a test UID
    if event_uid is None:
        # You might want to replace this with a known event UID from your calendar
        event_uid = "5A73AF42-11C4-4FD3-A6EA-6E5F2539E84D"
    
    # Send the get request
    response = events_client.get_event(event_uid)
    
    if is_debug:
        print("\n### TEST GET EVENT BY UID ###")
        print(f"Retrieving event with UID: {event_uid}")
        print(f"Status Code: {response.status_code}")
    
    assert response.status_code == 200, (
        f"Expected 200 when retrieving event by UID, got {response.status_code}: {response.text}"
    )

    result = response.json()
    if is_debug:
        print("Event retrieved successfully:")
        print(json.dumps(result, indent=4, sort_keys=True))
    return result


def test_get_event_by_uid(event_uid=None, is_debug=False):
    run_get_event_by_uid(event_uid=event_uid, is_debug=is_debug)


def run_get_events_by_time_range(start_datetime=None, end_datetime=None, is_debug=False):
    """Test the GET /events/ endpoint to retrieve events within a time range."""
    # If no datetime range is provided, use a default range (e.g., next 7 days)
    if start_datetime is None or end_datetime is None:
        from datetime import datetime, timedelta
        now = datetime.now()
        start_datetime = isoformat_seconds(now)
        end_datetime = isoformat_seconds(now + timedelta(days=7))
    
    # Send the get request with query parameters
    response = events_client.list_events(start_datetime, end_datetime)
    
    if is_debug:
        print("\n### TEST GET EVENTS BY TIME RANGE ###")
        print(f"Retrieving events between: {start_datetime} and {end_datetime}")
        print(f"Status Code: {response.status_code}")
    
    assert response.status_code == 200, (
        f"Expected 200 when retrieving events range, got {response.status_code}: {response.text}"
    )

    results = response.json()
    if is_debug:
        print(f"Retrieved {len(results)} events:")
        
        # Print details for up to 5 events
        for i, event in enumerate(results[:5]):
            print(f"\nEvent {i+1}:")
            print(f"UID: {event.get('uid')}")
            print(f"Summary: {event.get('summary')}")
            print(f"Start: {event.get('start')}")
            print(f"End: {event.get('end')}")
            print(f"Location: {event.get('location')}")
            
            if event.get('attendees'):
                print(f"Attendees: {len(event.get('attendees'))}")
                for attendee in event.get('attendees')[:3]:  # Show first 3 attendees only
                    print(f"  - {attendee.get('name') or attendee.get('email')}")
                if len(event.get('attendees')) > 3:
                    print(f"  - ... and {len(event.get('attendees')) - 3} more")
        
        if len(results) > 5:
            print(f"\n... and {len(results) - 5} more events")
    
    return results


def test_get_events_by_time_range(start_datetime=None, end_datetime=None, is_debug=False):
    run_get_events_by_time_range(
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        is_debug=is_debug
    )


def run_create_event(is_debug=False):
    """Test the POST /events/ endpoint to create a new event."""
    # Create a sample event
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    relative_reminder = {
        "type": "DISPLAY",
        "mode": "relative",
        "offset": "-PT10M",
        "relation": "START",
        "description": "Ping 10 minutes before start"
    }
    absolute_reminder = {
        "type": "EMAIL",
        "mode": "absolute",
        "fire_time": isoformat_seconds(now + timedelta(minutes=15)),
        "description": "Send email 15 minutes from now",
        "timezone": TEST_TIMEZONE
    }
    
    # Create event data as JSON
    event_data = {
        "uid": str(uuid.uuid4()),
        "summary": "Test Event from API Client",
        "description": "This is a test event created by the API client",
        "location": "Virtual Meeting Room",
        "start": isoformat_seconds(now),
        "end": isoformat_seconds(tomorrow),
        "all_day": False,
        "status": "CONFIRMED",
        "categories": ["TEST", "API", "CLIENT"],
        "reminders": [relative_reminder, absolute_reminder]
    }
    
    # Send the post request
    response = events_client.create_event(event_data)
    
    if is_debug:
        print("\n### TEST CREATE EVENT ###")
        print(f"Creating event with summary: {event_data['summary']}")
        print(f"Status Code: {response.status_code}")
    
    assert response.status_code in (200, 201), (
        f"Expected 200/201 when creating event, got {response.status_code}: {response.text}"
    )

    result = response.json()
    assert result.get("reminders"), "Expected reminders to round-trip from create_event response"
    absolute_with_timezone = [
        reminder for reminder in result["reminders"]
        if reminder.get("mode") == "absolute" and reminder.get("timezone") == TEST_TIMEZONE
    ]
    assert absolute_with_timezone, "Expected absolute reminder timezone to round-trip correctly"

    if is_debug:
        print("Event created successfully:")
        print(json.dumps(result, indent=4, sort_keys=True))
    return result


def test_create_event(is_debug=False):
    run_create_event(is_debug=is_debug)


def run_update_event(event_uid=None, is_debug=False):
    """Test the PUT /events/{uid} endpoint to update an existing event."""
    # First, create a new event or get an existing one
    if not event_uid:
        # Create a new event to update
        created_event = run_create_event(is_debug=is_debug)
        if not created_event:
            print("Failed to create a new event for update test")
            return None
        event_uid = created_event.get('uid')
    
    # Get the existing event to update
    existing_event = run_get_event_by_uid(event_uid, is_debug=is_debug)
    if not existing_event:
        print(f"No event found with UID: {event_uid}")
        return None
    
    # Make some changes to the event
    updated_data = existing_event.copy()
    updated_data['summary'] = f"{existing_event.get('summary')} (API Updated)"
    updated_data['description'] = f"{existing_event.get('description') or ''}\nUpdated via API on {datetime.now().isoformat()}"
    
    # If the event has categories, add a new one
    if 'categories' in updated_data and updated_data['categories']:
        updated_data['categories'].append("API-UPDATED")
    else:
        updated_data['categories'] = ["API-UPDATED"]
    
    if is_debug:
        print("\n### TEST UPDATE EVENT ###")
        print(f"Updating event with UID: {event_uid}")
        print(f"New summary: {updated_data['summary']}")
    
    # Send the put request
    response = events_client.update_event(event_uid, updated_data)
    
    if is_debug:
        print(f"Status Code: {response.status_code}")
    
    assert response.status_code == 200, (
        f"Expected 200 when updating event, got {response.status_code}: {response.text}"
    )

    result = response.json()
    if is_debug:
        print("Event updated successfully:")
        print(json.dumps(result, indent=4, sort_keys=True))
    return result


def test_update_event(event_uid=None, is_debug=False):
    run_update_event(event_uid=event_uid, is_debug=is_debug)


def run_delete_event(event_uid=None, is_debug=False):
    """Test the DELETE /events/{uid} endpoint to delete an event."""
    # First, create a new event or get an existing one
    if not event_uid:
        # Create a new event to delete
        created_event = run_create_event(is_debug=is_debug)
        if not created_event:
            print("Failed to create a new event for delete test")
            return None
        event_uid = created_event.get('uid')
    
    if is_debug:
        print("\n### TEST DELETE EVENT ###")
        print(f"Deleting event with UID: {event_uid}")
    
    # Send the delete request
    response = events_client.delete_event(event_uid)
    
    if is_debug:
        print(f"Status Code: {response.status_code}")
    
    # 204 No Content is the expected response for successful deletion
    assert response.status_code == 204, (
        f"Expected 204 when deleting event, got {response.status_code}: {response.text}"
    )

    if is_debug:
        print("Event deleted successfully")
    return True


def test_delete_event(event_uid=None, is_debug=False):
    run_delete_event(event_uid=event_uid, is_debug=is_debug)


# Run the tests
if __name__ == "__main__":
    # Test get_event_by_uid
    # You might want to replace this with a known event UID from your calendar
    event_uid = "5A73AF42-11C4-4FD3-A6EA-6E5F2539E84D"
    retrieved_event = run_get_event_by_uid(event_uid, is_debug=False)
    
    if retrieved_event is None:
        print(f"FAILURE: test_get_event_by_uid did not return an event")
        sys.exit(1)
    print(f"SUCCESS: test_get_event_by_uid returned event with summary: {retrieved_event.get('summary')}")
    
    # Test get_events_by_time_range
    # Use a default time range (next 7 days)
    from datetime import datetime, timedelta
    now = datetime.now()
    start_datetime = isoformat_seconds(now)
    end_datetime = isoformat_seconds(now + timedelta(days=7))
    
    retrieved_events = run_get_events_by_time_range(start_datetime, end_datetime, is_debug=False)
    
    if retrieved_events is None:
        print(f"FAILURE: test_get_events_by_time_range did not return any events")
        sys.exit(1)
    print(f"SUCCESS: test_get_events_by_time_range returned {len(retrieved_events)} events")
    
    # Test create_event
    created_event = run_create_event(is_debug=False)
    
    if created_event is None:
        print(f"FAILURE: test_create_event did not create an event")
        sys.exit(1)
    print(f"SUCCESS: test_create_event created event with summary: {created_event.get('summary')}")
    
    # Test update_event (using the event we just created)
    updated_event = run_update_event(created_event.get('uid'), is_debug=False)
    
    if updated_event is None:
        print(f"FAILURE: test_update_event did not update the event")
        sys.exit(1)
    print(f"SUCCESS: test_update_event updated event with summary: {updated_event.get('summary')}")
    
    # Test delete_event (using the event we just updated)
    deleted = run_delete_event(updated_event.get('uid'), is_debug=False)
    
    if deleted is None:
        print(f"FAILURE: test_delete_event did not delete the event")
        sys.exit(1)
    print(f"SUCCESS: test_delete_event deleted the event with UID: {updated_event.get('uid')}")
