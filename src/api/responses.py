# Shared response metadata to reduce duplication across routers.

CONTACT_ERROR_RESPONSES = {
    401: {
        "description": "Authentication failed",
        "content": {"application/json": {"example": {"detail": "Invalid credentials"}}},
    },
    403: {
        "description": "Authorization refused",
        "content": {"application/json": {"example": {"detail": "Access denied to addressbook"}}},
    },
    404: {
        "description": "Contact not found",
        "content": {"application/json": {"example": {"detail": "Contact not found"}}},
    },
    503: {
        "description": "Server error or connection issue",
        "content": {"application/json": {"example": {"detail": "Backend connection failed"}}},
    },
}

EVENT_ERROR_RESPONSES = {
    401: {
        "description": "Authentication failed",
        "content": {"application/json": {"example": {"detail": "Invalid credentials"}}},
    },
    403: {
        "description": "Authorization refused",
        "content": {"application/json": {"example": {"detail": "Access denied to calendar"}}},
    },
    404: {
        "description": "Event not found",
        "content": {"application/json": {"example": {"detail": "Event not found"}}},
    },
    503: {
        "description": "Server error or connection issue",
        "content": {"application/json": {"example": {"detail": "Backend connection failed"}}},
    },
}

TASK_ERROR_RESPONSES = {
    401: {
        "description": "Authentication failed",
        "content": {"application/json": {"example": {"detail": "Invalid credentials"}}},
    },
    403: {
        "description": "Authorization refused",
        "content": {"application/json": {"example": {"detail": "Access denied to task list"}}},
    },
    404: {
        "description": "Task not found",
        "content": {"application/json": {"example": {"detail": "Task not found"}}},
    },
    503: {
        "description": "Server error or connection issue",
        "content": {"application/json": {"example": {"detail": "Backend connection failed"}}},
    },
}
