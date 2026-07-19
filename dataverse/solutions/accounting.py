from pydantic import BaseModel
from typing import Dict
import logging
import sys


publisher = {
    "uniquename": "accounting", 
    "friendlyname": "Accounting",
    "customizationprefix": "acc", 
    "description": "The accounting information for massflows",
}



def get_solution(publisher_id:str)-> Dict[str,str]:

    solution = {
        "uniquename": "acc_AccountsPayable", 
        "friendlyname": "AccountsPayable",
        "version": "1.0.0.0",
        "publisherid@odata.bind": f"/publishers({publisher_id})"
    }

    return solution