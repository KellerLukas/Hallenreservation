import json
from onepassword import OnePassword
from onepassword.utils import read_bash_return
from typing import Optional


class ImprovedOnePassword(OnePassword):
    @staticmethod
    def get_item(uuid: str | bytes, fields: str | bytes | list | None = None, vault_uuid: Optional[str]=None):
        """
        Helper function to get a certain field, you can find the UUID you need using list_items

        :param uuid: Uuid of the item you wish to get, no vault needed
        :param fields: To return only certain detail use either a specific field or list of them
            (Optional, default=None which means all fields returned)
        :para
        :return: Dictionary of the item with requested fields
        """
        if isinstance(fields, list):
            item_list = json.loads(read_bash_return(
                "op item get {} --format=json --fields label={}{}".format(uuid, ",label=".join(fields), f" --vault {vault_uuid}" if vault_uuid else ""),
                single=False))
            item = {}
            if isinstance(item_list, dict):
                item[fields[0]] = item_list["value"]
            else:
                for i in item_list:
                    item[i["id"]] = i["value"]
        elif isinstance(fields, str):
            item = {
                fields: read_bash_return(
                    "op item get {} --fields label={}{}".format(uuid, fields, f" --vault {vault_uuid}" if vault_uuid else ""), single=False).rstrip('\n')
            }
        else:
            item = json.loads(read_bash_return("op item get {} --format=json{}".format(uuid, f" --vault {vault_uuid}" if vault_uuid else ""), single=False))
        return item