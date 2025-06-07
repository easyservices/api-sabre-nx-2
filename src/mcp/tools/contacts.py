from typing import List, Optional
from fastapi.security import HTTPBasicCredentials
from fastapi import HTTPException
from src.common.sec import authenticate_with_nextcloud
from src.models.contact import Contact
from .. import mcp
from src.nextcloud.contacts import get_all_contacts as nx_get_all_contacts
from src import logger


@mcp.tool()
def calculate_bmi(weight_kg: float, height_m: float) -> float:
    """Calculate BMI given weight in kg and height in meters"""
    return weight_kg / (height_m**2)

@mcp.tool()
async def get_all_contacts(credentials: HTTPBasicCredentials, addressbook_name: Optional[str] = None) -> List[Contact]:
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"get_all_contacts: user_info: {user_info}")
    
    try:
        contacts = await nx_get_all_contacts(
            credentials=credentials
        )
    except Exception as e:
        # Handle potential errors during the fetch from Nextcloud
        res_txt = f"Error fetching contacts from Nextcloud: {e}"
        logger.error(res_txt)
        raise HTTPException(status_code=503, detail="Could not retrieve contacts from backend")

    return contacts