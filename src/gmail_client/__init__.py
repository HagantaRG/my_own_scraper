import os
from pathlib import Path

import googleapiclient.discovery
import requests
from google.oauth2 import service_account


class GoogleClient:
    credential_filepath: str

    def __init__(self, creds_filepath: str):
        self.credential_filepath = creds_filepath

    def get_spreadsheet_as_csv(
        self, spreadsheet_id: str, target_folder: Path | str, sheet_name: str
    ) -> list[Path]:
        scope = ["https://www.googleapis.com/auth/drive.readonly"]
        path_list: list[Path] = []
        credentials = service_account.Credentials.from_service_account_file(
            self.credential_filepath, scopes=scope
        )
        service = googleapiclient.discovery.build(
            "sheets", "v4", credentials=credentials
        )
        result = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        spreadsheet_url: str = result["spreadsheetUrl"]
        headers = {
            "Authorization": "Bearer " + credentials.token,
        }
        url: str = spreadsheet_url.replace("edit", "export")

        # I am too lazy to handle this properly. The keywords CSV should only have one sheet associated with it ANYWAY.
        sheet_num: int = 0
        for sheet in result["sheets"]:
            sheet_num += 1
            params = {
                "id": spreadsheet_id,
                "format": "csv",
                "gid": sheet["properties"]["sheetId"],
            }
            response = requests.get(url, headers=headers, params=params)
            filepath: Path = Path(f"{target_folder}/{sheet_name}-{sheet_num}.csv")
            if not os.path.exists(target_folder):
                os.mkdir(target_folder)
            with open(filepath, "wb") as csvFile:
                csvFile.write(response.content)
                path_list.append(filepath)
        return path_list
