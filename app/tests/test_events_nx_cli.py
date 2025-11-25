# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Manual API endpoint test script for the Nextcloud CalDAV events FastAPI app.

Results are printed to stdout for manual inspection.
"""

import sys
import json
import asyncio

from src.nextcloud import events
from src.common.config import UsersSettings # Import your config settings
from fastapi.security import HTTPBasicCredentials

# Import Event model for type checking
from src.models.event import Event, Reminder
from datetime import datetime, timedelta

TEST_TIMEZONE = "Europe/Paris"

settings = UsersSettings()

""" TESTING API ENDPOINTS """

async def get_event_by_uid_test(event_uid=None, is_debug=False):
    """Test the get_event_by_uid function to retrieve a single event by UID."""
    if is_debug:
        print("### TEST get_event_by_uid ###")
        print(f"Using user settings for: test4me")

    try:
        # If no event UID is provided, use a test UID
        if event_uid is None:
            # You might want to replace this with a known event UID from your calendar
            event_uid = "5A73AF42-11C4-4FD3-A6EA-6E5F2539E84D"
            
        if is_debug:
            print(f"Retrieving event with UID: {event_uid}")
        
        # Call the get_event_by_uid function
        # Create HTTPBasicCredentials object
        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD
        )
        
        retrieved_event = await events.get_event_by_uid(
            credentials,
            event_uid
        )
        
        # --- Nice Printing Logic ---
        if is_debug:
            print("\n--- Get Event By UID Result ---")
            if retrieved_event:
                print(f"Event retrieved successfully with UID: {retrieved_event.uid}")
                print(f"Summary: {retrieved_event.summary}")
                print(f"URL: {retrieved_event.url}")
                print(json.dumps(retrieved_event.model_dump(), indent=4))
            else:
                print(f"No event found with UID: {event_uid}")
            print("-------------")
        
        return retrieved_event
        
    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        # If it's an HTTPException from your function, print details
        if hasattr(e, 'status_code') and hasattr(e, 'detail'):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return None


async def create_event_test(is_debug=False):
    """Test the create_event function to create a new event."""
    if is_debug:
        print("### TEST create_event ###")
        print(f"Using user settings for: test4me")

    try:
        # Create a sample event
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        relative_reminder = Reminder(
            type="DISPLAY",
            mode="relative",
            offset="-PT5M",
            relation="START",
            description="Notify 5 minutes early"
        )
        absolute_reminder = Reminder(
            type="EMAIL",
            mode="absolute",
            fire_time=(now + timedelta(minutes=30)).isoformat(),
            description="Email reminder 30 minutes before end",
            timezone=TEST_TIMEZONE
        )
        
        # Create a new event with a generated UID
        event = Event(
            uid=Event.generate_uid(),
            summary="Test Event from API",
            description="This is a test event created by the API",
            location="Virtual Meeting",
            start=now.isoformat(),
            end=tomorrow.isoformat(),
            all_day=False,
            status="CONFIRMED",
            categories=["TEST", "API"],
            reminders=[relative_reminder, absolute_reminder]
        )
        
        if is_debug:
            print(f"Creating event with summary: {event.summary}")
            print(f"Start: {event.start}")
            print(f"End: {event.end}")
        
        # Call the create_event function
        # Create HTTPBasicCredentials object
        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD
        )
        
        created_event = await events.create_event(
            credentials,
            event
        )
        
        # --- Nice Printing Logic ---
        if is_debug:
            print("\n--- Create Event Result ---")
            print(f"Event created successfully with UID: {created_event.uid}")
            print(f"Summary: {created_event.summary}")
            print(f"URL: {created_event.url}")
            print("-------------")
        assert created_event.reminders, "Expected reminders to be returned when creating event"
        for reminder in created_event.reminders:
            assert reminder.mode in ("absolute", "relative"), "Reminder mode missing after creation"
        assert any(
            reminder.mode == "absolute" and reminder.timezone == TEST_TIMEZONE
            for reminder in created_event.reminders
        ), "Expected absolute reminder timezone to round-trip"
        
        return created_event
        
    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        # If it's an HTTPException from your function, print details
        if hasattr(e, 'status_code') and hasattr(e, 'detail'):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return None


async def update_event_test(event_uid=None, is_debug=False):
    """Test the update_event function to update an existing event."""
    if is_debug:
        print("### TEST update_event ###")
        print(f"Using user settings for: test4me")

    try:
        # First, get an existing event or create a new one if no UID is provided
        # Create HTTPBasicCredentials object
        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD
        )
        
        if event_uid:
            # Get an existing event
            existing_event = await get_event_by_uid_test(event_uid, is_debug=is_debug)
            if not existing_event:
                print(f"No event found with UID: {event_uid}")
                return None
        else:
            # Create a new event to update
            existing_event = await create_event_test(is_debug=is_debug)
            if not existing_event:
                print("Failed to create a new event for update test")
                return None
        
        if is_debug:
            print(f"\nModifying event with UID: {existing_event.uid}")
            print(f"Original summary: {existing_event.summary}")
        
        # Make some changes to the event
        updated_event = existing_event.model_copy(deep=True)
        updated_event.summary = f"{existing_event.summary} (Updated)"
        updated_event.description = f"{existing_event.description or ''}\nUpdated on {datetime.now().isoformat()}"
        
        # If the event has categories, add a new one
        if updated_event.categories:
            updated_event.categories.append("UPDATED")
        else:
            updated_event.categories = ["UPDATED"]
        
        if is_debug:
            print(f"New summary: {updated_event.summary}")
            print(f"Updated categories: {updated_event.categories}")
        
        # Call the update_event function
        result = await events.update_event(
            credentials,
            updated_event
        )
        
        # --- Nice Printing Logic ---
        if is_debug:
            print("\n--- Update Event Result ---")
            print(f"Event updated successfully with UID: {result.uid}")
            print(f"Summary: {result.summary}")
            print(f"URL: {result.url}")
            print("-------------")
        
        return result
        
    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        # If it's an HTTPException from your function, print details
        if hasattr(e, 'status_code') and hasattr(e, 'detail'):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return None


async def get_events_by_time_range_test(start_datetime=None, end_datetime=None, is_debug=False):
    """Test the get_events_by_time_range function to retrieve events within a time range."""
    if is_debug:
        print("### TEST get_events_by_time_range ###")
        print(f"Using user settings for: test4me")

    try:
        # If no datetime range is provided, use a default range (e.g., next 7 days)
        if start_datetime is None or end_datetime is None:
            from datetime import datetime, timedelta
            now = datetime.now()
            start_datetime = now.isoformat()
            end_datetime = (now + timedelta(days=7)).isoformat()
            
        if is_debug:
            print(f"Retrieving events between: {start_datetime} and {end_datetime}")
        
        # Call the get_events_by_time_range function
        # Create HTTPBasicCredentials object
        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD
        )
        
        retrieved_events = await events.get_events_by_time_range(
            credentials,
            start_datetime,
            end_datetime
        )
        
        # --- Nice Printing Logic ---
        if is_debug:
            print("\n--- Get Events By Time Range Result ---")
            print(f"Found {len(retrieved_events)} events in the specified time range")
            
            for i, event in enumerate(retrieved_events):
                print(f"\nEvent {i+1}:")
                print(f"UID: {event.uid}")
                print(f"Summary: {event.summary}")
                print(f"Start: {event.start}")
                print(f"End: {event.end}")
                print(f"Location: {event.location}")
                
                if event.attendees:
                    print(f"Attendees: {len(event.attendees)}")
                    for attendee in event.attendees[:3]:  # Show first 3 attendees only
                        print(f"  - {attendee.name or attendee.email}")
                    if len(event.attendees) > 3:
                        print(f"  - ... and {len(event.attendees) - 3} more")
                
                if i >= 4 and len(retrieved_events) > 5:  # Show only first 5 events in detail
                    print(f"\n... and {len(retrieved_events) - 5} more events")
                    break
            
            print("-------------")
        
        return retrieved_events
        
    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        # If it's an HTTPException from your function, print details
        if hasattr(e, 'status_code') and hasattr(e, 'detail'):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return None


async def delete_event_test(event_uid=None, is_debug=False):
    """Test the delete_event function to delete an event."""
    if is_debug:
        print("### TEST delete_event ###")
        print(f"Using user settings for: test4me")

    try:
        # First, create a new event if no UID is provided
        # Create HTTPBasicCredentials object
        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD
        )
        
        if not event_uid:
            # Create a new event to delete
            created_event = await create_event_test(is_debug=is_debug)
            if not created_event:
                print("Failed to create a new event for delete test")
                return False
            event_uid = created_event.uid
        
        if is_debug:
            print(f"\nDeleting event with UID: {event_uid}")
        
        # Call the delete_event function
        result = await events.delete_event(
            credentials,
            event_uid
        )
        
        # --- Nice Printing Logic ---
        if is_debug:
            print("\n--- Delete Event Result ---")
            if result:
                print(f"Event deleted successfully with UID: {event_uid}")
            else:
                print(f"Event with UID {event_uid} not found or could not be deleted")
            print("-------------")
        
        return result
        
    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        # If it's an HTTPException from your function, print details
        if hasattr(e, 'status_code') and hasattr(e, 'detail'):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return False


if __name__ == "__main__":
    # Run the tests and check for success/failure
    
    # Test get_event_by_uid
    # You might want to replace this with a known event UID from your calendar
    event_uid = "5A73AF42-11C4-4FD3-A6EA-6E5F2539E84D"
    retrieved_event = asyncio.run(get_event_by_uid_test(event_uid, is_debug=False))
    
    if retrieved_event is None:
        print(f"FAILURE: get_event_by_uid_test did not return an event")
        sys.exit(1)
    print(f"SUCCESS: get_event_by_uid_test returned event with summary: {retrieved_event.summary}")
    
    # Test get_events_by_time_range
    # Use a default time range (next 7 days)
    from datetime import datetime, timedelta
    now = datetime.now()
    start_datetime = now.isoformat()
    end_datetime = (now + timedelta(days=7)).isoformat()
    
    retrieved_events = asyncio.run(get_events_by_time_range_test(start_datetime, end_datetime, is_debug=False))
    
    if retrieved_events is None:
        print(f"FAILURE: get_events_by_time_range_test did not return any events")
        sys.exit(1)
    print(f"SUCCESS: get_events_by_time_range_test returned {len(retrieved_events)} events")
    
    # Test create_event
    created_event = asyncio.run(create_event_test(is_debug=False))
    
    if created_event is None:
        print(f"FAILURE: create_event_test did not create an event")
        sys.exit(1)
    print(f"SUCCESS: create_event_test created event with summary: {created_event.summary}")
    
    # Test update_event (using the event we just created)
    updated_event = asyncio.run(update_event_test(created_event.uid, is_debug=False))
    
    if updated_event is None:
        print(f"FAILURE: update_event_test did not update the event")
        sys.exit(1)
    print(f"SUCCESS: update_event_test updated event with summary: {updated_event.summary}")
    
    # Test delete_event (using the event we just updated)
    deleted = asyncio.run(delete_event_test(updated_event.uid, is_debug=False))
    
    if not deleted:
        print(f"FAILURE: delete_event_test did not delete the event")
        sys.exit(1)
    print(f"SUCCESS: delete_event_test deleted the event with UID: {updated_event.uid}")
