# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Manual API endpoint test script for the Nextcloud CalDAV tasks (VTODO) FastAPI app.

Results are printed to stdout for manual inspection.
"""

import sys
import json
import asyncio
from datetime import datetime, timedelta

from src.nextcloud import tasks
from src.common.config import UsersSettings
from fastapi.security import HTTPBasicCredentials
from src.models.task import Task

settings = UsersSettings()
CALENDAR_NAME = settings.USERS["test4me"].NEXTCLOUD_CALENDAR or "personal"


async def get_task_by_uid_test(task_uid=None, is_debug=False):
    """Test the get_task_by_uid function to retrieve a single task by UID."""
    if is_debug:
        print("### TEST get_task_by_uid ###")
        print(f"Using user settings for: test4me")

    try:
        if task_uid is None:
            task_uid = Task.generate_uid()

        if is_debug:
            print(f"Retrieving task with UID: {task_uid}")

        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD,
        )

        retrieved_task = await tasks.get_task_by_uid(
            credentials,
            task_uid,
            calendar_name=CALENDAR_NAME,
        )

        if is_debug:
            print("\n--- Get Task By UID Result ---")
            if retrieved_task:
                print(f"Task retrieved successfully with UID: {retrieved_task.uid}")
                print(f"Summary: {retrieved_task.summary}")
                print(f"URL: {retrieved_task.url}")
                print(json.dumps(retrieved_task.model_dump(), indent=4))
            else:
                print(f"No task found with UID: {task_uid}")
            print("-------------")

        return retrieved_task

    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        if hasattr(e, "status_code") and hasattr(e, "detail"):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return None


async def create_task_test(is_debug=False):
    """Test the create_task function to create a new task."""
    if is_debug:
        print("### TEST create_task ###")
        print(f"Using user settings for: test4me")

    try:
        now = datetime.now()
        due = now + timedelta(days=1)

        task = Task(
            uid=Task.generate_uid(),
            summary="Test Task from API",
            description="This is a test task created by the API",
            start=now.isoformat(),
            due=due.isoformat(),
            all_day=False,
            status="NEEDS-ACTION",
            categories=["TEST", "API"],
            percent_complete=0,
        )

        if is_debug:
            print(f"Creating task with summary: {task.summary}")
            print(f"Start: {task.start}")
            print(f"Due: {task.due}")

        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD,
        )

        created_task = await tasks.create_task(
            credentials,
            task,
            calendar_name=CALENDAR_NAME,
        )

        if is_debug:
            print("\n--- Create Task Result ---")
            print(f"Task created successfully with UID: {created_task.uid}")
            print(f"Summary: {created_task.summary}")
            print(f"URL: {created_task.url}")
            print("-------------")

        return created_task

    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        if hasattr(e, "status_code") and hasattr(e, "detail"):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return None


async def update_task_test(task_uid=None, is_debug=False):
    """Test the update_task function to update an existing task."""
    if is_debug:
        print("### TEST update_task ###")
        print(f"Using user settings for: test4me")

    try:
        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD,
        )

        if task_uid:
            existing_task = await get_task_by_uid_test(task_uid, is_debug=is_debug)
            if not existing_task:
                print(f"No task found with UID: {task_uid}")
                return None
        else:
            existing_task = await create_task_test(is_debug=is_debug)
            if not existing_task:
                print("Failed to create a new task for update test")
                return None

        if is_debug:
            print(f"\nModifying task with UID: {existing_task.uid}")
            print(f"Original summary: {existing_task.summary}")

        updated_task = existing_task.model_copy(deep=True)
        updated_task.summary = f"{existing_task.summary} (Updated)"
        updated_task.description = f"{existing_task.description or ''}\nUpdated on {datetime.now().isoformat()}"
        updated_task.percent_complete = 50

        if updated_task.categories:
            updated_task.categories.append("UPDATED")
        else:
            updated_task.categories = ["UPDATED"]

        if is_debug:
            print(f"New summary: {updated_task.summary}")
            print(f"Updated categories: {updated_task.categories}")

        result = await tasks.update_task(
            credentials,
            updated_task,
            calendar_name=CALENDAR_NAME,
        )

        if is_debug:
            print("\n--- Update Task Result ---")
            print(f"Task updated successfully with UID: {result.uid}")
            print(f"Summary: {result.summary}")
            print(f"URL: {result.url}")
            print("-------------")

        return result

    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        if hasattr(e, "status_code") and hasattr(e, "detail"):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return None


async def get_tasks_by_time_range_test(start_datetime=None, end_datetime=None, is_debug=False):
    """Test the get_tasks_by_time_range function to retrieve tasks within a time range."""
    if is_debug:
        print("### TEST get_tasks_by_time_range ###")
        print(f"Using user settings for: test4me")

    try:
        if start_datetime is None or end_datetime is None:
            now = datetime.now()
            start_datetime = now.isoformat()
            end_datetime = (now + timedelta(days=7)).isoformat()

        if is_debug:
            print(f"Retrieving tasks between: {start_datetime} and {end_datetime}")

        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD,
        )

        retrieved_tasks = await tasks.get_tasks_by_time_range(
            credentials,
            start_datetime,
            end_datetime,
            calendar_name=CALENDAR_NAME,
        )

        if is_debug:
            print("\n--- Get Tasks By Time Range Result ---")
            if retrieved_tasks is not None:
                print(f"Retrieved {len(retrieved_tasks)} tasks")
            print("-------------")

        return retrieved_tasks

    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        if hasattr(e, "status_code") and hasattr(e, "detail"):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return None


async def delete_task_test(task_uid=None, is_debug=False):
    """Test the delete_task function to delete a task."""
    if is_debug:
        print("### TEST delete_task ###")
        print(f"Using user settings for: test4me")

    try:
        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD,
        )

        if task_uid is None:
            created_task = await create_task_test(is_debug=is_debug)
            if created_task is None:
                print("Failed to create a new task for delete test")
                return False
            task_uid = created_task.uid

        if is_debug:
            print(f"\nDeleting task with UID: {task_uid}")

        result = await tasks.delete_task(
            credentials,
            task_uid,
            calendar_name=CALENDAR_NAME,
        )

        if is_debug:
            print("\n--- Delete Task Result ---")
            if result:
                print(f"Task deleted successfully with UID: {task_uid}")
            else:
                print(f"Task with UID {task_uid} not found or could not be deleted")
            print("-------------")

        return result

    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        if hasattr(e, "status_code") and hasattr(e, "detail"):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return False


if __name__ == "__main__":
    task_uid = Task.generate_uid()
    retrieved_task = asyncio.run(get_task_by_uid_test(task_uid, is_debug=False))

    if retrieved_task is None:
        print("FAILURE: get_task_by_uid_test did not return a task")
        sys.exit(1)
    print(f"SUCCESS: get_task_by_uid_test returned task with UID: {retrieved_task.uid}")

    now = datetime.now()
    start_datetime = now.isoformat()
    end_datetime = (now + timedelta(days=7)).isoformat()

    retrieved_tasks = asyncio.run(get_tasks_by_time_range_test(start_datetime, end_datetime, is_debug=False))

    if retrieved_tasks is None:
        print("FAILURE: get_tasks_by_time_range_test did not return any tasks")
        sys.exit(1)
    print(f"SUCCESS: get_tasks_by_time_range_test returned {len(retrieved_tasks)} tasks")

    created_task = asyncio.run(create_task_test(is_debug=False))

    if created_task is None:
        print("FAILURE: create_task_test did not create a task")
        sys.exit(1)
    print(f"SUCCESS: create_task_test created task with summary: {created_task.summary}")

    updated_task = asyncio.run(update_task_test(created_task.uid, is_debug=False))

    if updated_task is None:
        print("FAILURE: update_task_test did not update the task")
        sys.exit(1)
    print(f"SUCCESS: update_task_test updated task with summary: {updated_task.summary}")

    deleted = asyncio.run(delete_task_test(updated_task.uid, is_debug=False))

    if not deleted:
        print("FAILURE: delete_task_test did not delete the task")
        sys.exit(1)
    print(f"SUCCESS: delete_task_test deleted the task with UID: {updated_task.uid}")
